from pathlib import Path
import re
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from yakuza.models import AuditLog, InvoiceSetting, Settings, UserProfile
from yakuza.views import RECOVERY_QUESTIONS
from yakuza.admin import UserSecurityProfileForm, UserSecurityProfileInline
from django.contrib import admin


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='recovery-user', password='Old!Password927')
        self.profile = UserProfile.objects.create(
            user=self.user,
            mobile_number='9876543210',
            recovery_question=RECOVERY_QUESTIONS[0],
            recovery_answer_hash=make_password('bluebird'),
        )

    def identify(self, mobile='9876543210'):
        return self.client.post(reverse('yakuza:forgot_password'), {'mobile_number': mobile})

    def test_login_page_and_forgot_password_link(self):
        response = self.client.get(reverse('yakuza:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot Password?')
        self.assertNotContains(response, 'Login with Security Option')
        self.assertNotContains(response, 'login-message-source')
        self.assertEqual(self.client.get(reverse('yakuza:forgot_password')).status_code, 200)

    def test_existing_username_password_login_still_works(self):
        response = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': 'Old!Password927',
        })
        self.assertRedirects(response, reverse('yakuza:dashboard'))

    def test_invalid_login_message_is_rendered_only_as_popup_source(self):
        response = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': 'incorrect-password',
        })
        self.assertContains(response, 'login-message-source')
        self.assertContains(response, 'Invalid username or password!')
        self.assertNotContains(response, 'role="status"')

    def test_unknown_mobile_has_same_generic_verification_page(self):
        response = self.identify('9999999999')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot Password?')
        self.assertContains(response, 'Mobile number does not match any registered account.')
        self.assertNotIn('recovery_user_id', self.client.session)

    def test_registered_mobile_proceeds_to_question_step(self):
        response = self.identify()
        self.assertContains(response, 'Verify Your Account')
        self.assertEqual(self.client.session['recovery_user_id'], self.user.id)

    def test_wrong_answers_lock_the_account(self):
        self.identify()
        for _ in range(5):
            self.client.post(reverse('yakuza:verify_recovery_answer'), {
                'recovery_question': RECOVERY_QUESTIONS[0], 'recovery_answer': 'wrong',
            })
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.recovery_locked_until)
        response = self.client.post(reverse('yakuza:verify_recovery_answer'), {
            'recovery_question': RECOVERY_QUESTIONS[0], 'recovery_answer': 'bluebird',
        })
        self.assertContains(response, 'The answer could not be verified')

    def test_verified_answer_can_reset_password_once_and_login(self):
        self.identify()
        response = self.client.post(reverse('yakuza:verify_recovery_answer'), {
            'recovery_question': RECOVERY_QUESTIONS[0], 'recovery_answer': '  BLUEBIRD  ',
        })
        self.assertRedirects(response, reverse('yakuza:reset_password'))
        response = self.client.post(reverse('yakuza:reset_password'), {
            'new_password': 'New!SecurePass2026', 'confirm_password': 'not-matching',
        })
        self.assertContains(response, 'passwords do not match')
        response = self.client.post(reverse('yakuza:reset_password'), {
            'new_password': '12345', 'confirm_password': '12345',
        })
        self.assertContains(response, 'at least 6 characters')
        response = self.client.post(reverse('yakuza:reset_password'), {
            'new_password': 'abcdefgh', 'confirm_password': 'abcdefgh',
        }, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('yakuza:login'))
        self.assertContains(response, 'class="login-message-source"')
        self.assertContains(response, 'Your password has been reset. Please log in with your new password.')
        self.assertNotContains(response, 'role="status"')
        login_script = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'login.js').read_text(encoding='utf-8')
        self.assertIn('showToast(null, source.textContent.trim(), type, 3000', login_script)
        self.assertIn('duration = 3000', login_script)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('abcdefgh'))
        self.assertFalse(self.user.check_password('Old!Password927'))
        self.assertNotEqual(self.user.password, 'New!SecurePass2026')
        old_login = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': 'Old!Password927',
        })
        self.assertEqual(old_login.status_code, 200)
        new_login = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': 'abcdefgh',
        })
        self.assertRedirects(new_login, reverse('yakuza:dashboard'))
        self.assertEqual(self.client.get(reverse('yakuza:reset_password')).status_code, 200)

    def test_reset_page_has_independent_show_hide_controls(self):
        self.identify()
        self.client.post(reverse('yakuza:verify_recovery_answer'), {
            'recovery_question': RECOVERY_QUESTIONS[0], 'recovery_answer': 'bluebird',
        })
        response = self.client.get(reverse('yakuza:reset_password'))
        self.assertContains(response, 'data-password-target="newPassword"')
        self.assertContains(response, 'data-password-target="confirmPassword"')
        self.assertContains(response, 'minlength="6"')
        self.assertContains(response, 'js/forgot_password.js')
        script = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'forgot_password.js').read_text()
        self.assertIn("input.type = show ? 'text' : 'password'", script)
        self.assertIn("button.dataset.passwordTarget", script)

    def test_reset_is_not_available_without_verification(self):
        response = self.client.post(reverse('yakuza:reset_password'), {
            'new_password': 'New!SecurePass2026', 'confirm_password': 'New!SecurePass2026',
        })
        self.assertContains(response, 'recovery session expired')

    def test_new_registration_requires_recovery_question_and_answer(self):
        response = self.client.post(reverse('yakuza:register'),
            data='{"username":"new-user","password":"long-password","confirm_password":"long-password"}',
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Choose a recovery question', status_code=400)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SecurityQuestionAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin-managed-user', password='OriginalPassword')
        self.profile = UserProfile.objects.create(user=self.user, mobile_number='9876543210')

    def test_superuser_can_find_users_and_configure_security_in_admin(self):
        superuser = User.objects.create_superuser(username='security-admin', password='AdminPassword')
        self.client.force_login(superuser)
        response = self.client.get('/admin/auth/user/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin-managed-user')
        self.assertContains(response, '9876543210')
        self.assertContains(response, 'Security details configured')

        form = UserSecurityProfileForm(data={
            'recovery_question': RECOVERY_QUESTIONS[0],
            'recovery_answer': '  Blue   Bird  ',
        }, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.recovery_question, RECOVERY_QUESTIONS[0])
        self.assertTrue(check_password('blue bird', profile.recovery_answer_hash))
        self.assertNotEqual(profile.recovery_answer_hash, 'blue bird')

    def test_admin_answer_is_write_only_and_blank_answer_preserves_hash(self):
        self.profile.recovery_question = RECOVERY_QUESTIONS[0]
        self.profile.recovery_answer_hash = make_password('existing answer')
        self.profile.save()
        form = UserSecurityProfileForm(instance=self.profile)
        self.assertEqual(form['recovery_answer'].value(), None)
        old_hash = self.profile.recovery_answer_hash
        update = UserSecurityProfileForm(data={
            'recovery_question': RECOVERY_QUESTIONS[0], 'recovery_answer': '',
        }, instance=self.profile)
        self.assertTrue(update.is_valid(), update.errors)
        self.assertEqual(update.save().recovery_answer_hash, old_hash)

    def test_only_superuser_can_manage_security_inline(self):
        inline = UserSecurityProfileInline(User, admin.site)
        request = RequestFactory().get('/admin/auth/user/')
        request.user = User.objects.create_user(username='staff', password='StaffPassword', is_staff=True)
        self.assertFalse(inline.has_view_permission(request, self.user))
        self.assertFalse(inline.has_change_permission(request, self.user))
        self.assertFalse(inline.has_add_permission(request, self.user))
        request.user = User.objects.create_superuser(username='security-admin', password='AdminPassword')
        self.assertTrue(inline.has_view_permission(request, self.user))
        self.assertTrue(inline.has_change_permission(request, self.user))
        self.assertTrue(inline.has_add_permission(request, self.user))

        profile_admin = admin.site._registry[UserProfile]
        profile_form = profile_admin.get_form(request)
        self.assertNotIn('recovery_question', profile_form.base_fields)
        self.assertNotIn('recovery_answer_hash', profile_form.base_fields)

    def test_admin_configured_answer_works_in_password_recovery(self):
        form = UserSecurityProfileForm(data={
            'recovery_question': RECOVERY_QUESTIONS[1],
            'recovery_answer': '  New   York  ',
        }, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        response = self.client.post(reverse('yakuza:forgot_password'), {'mobile_number': '9876543210'})
        self.assertContains(response, 'Verify Your Account')
        response = self.client.post(reverse('yakuza:verify_recovery_answer'), {
            'recovery_question': RECOVERY_QUESTIONS[1], 'recovery_answer': 'new york',
        })
        self.assertRedirects(response, reverse('yakuza:reset_password'))


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SaveUserCsrfTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='save-user-admin', password='AdminPassword927')
        UserProfile.objects.create(user=self.admin, role=UserProfile.RoleChoices.SUPER_ADMIN)
        Settings.objects.create()
        InvoiceSetting.objects.create()
        self.client = self.client_class(enforce_csrf_checks=True)
        self.client.force_login(self.admin)

    def get_form_csrf_token(self):
        page = self.client.get(reverse('yakuza:settings'))
        self.assertEqual(page.status_code, 200)
        match = re.search(
            r'<form id="form-user-modal">\s*<input[^>]*name="csrfmiddlewaretoken"[^>]*value="([^"]+)"',
            page.content.decode(),
        )
        self.assertIsNotNone(match, 'The Add User form should render a CSRF token.')
        return match.group(1)

    def user_payload(self):
        return {
            'csrfmiddlewaretoken': self.get_form_csrf_token(),
            'fullname': 'Created Superuser',
            'username': 'created-superuser',
            'password': 'abcdefgh',
            'confirm_password': 'abcdefgh',
            'role': UserProfile.RoleChoices.SUPER_ADMIN,
            'status': 'Active',
        }

    def test_authorized_user_creation_succeeds_with_rendered_csrf_token(self):
        payload = self.user_payload()
        response = self.client.post(
            reverse('yakuza:save_user_ajax'),
            payload,
            HTTP_X_CSRFTOKEN=payload['csrfmiddlewaretoken'],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        created = User.objects.get(username='created-superuser')
        self.assertTrue(created.is_superuser)
        self.assertEqual(created.userprofile.role, UserProfile.RoleChoices.SUPER_ADMIN)

    def test_save_user_post_without_csrf_token_is_forbidden(self):
        response = self.client.post(reverse('yakuza:save_user_ajax'), {
            'fullname': 'Created Superuser',
            'username': 'created-superuser',
            'password': 'Secure!Password927',
            'confirm_password': 'Secure!Password927',
            'role': UserProfile.RoleChoices.SUPER_ADMIN,
            'status': 'Active',
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='created-superuser').exists())

    def test_creation_rejects_password_shorter_than_six_and_mismatched_confirmation(self):
        short_payload = self.user_payload()
        short_payload.update(username='short-password-user', password='abcde', confirm_password='abcde')
        short_response = self.client.post(reverse('yakuza:save_user_ajax'), short_payload)
        self.assertEqual(short_response.status_code, 400)
        self.assertIn('at least 6 characters', short_response.json()['message'])

        mismatch_payload = self.user_payload()
        mismatch_payload.update(username='mismatch-password-user', confirm_password='abcdefghi')
        mismatch_response = self.client.post(reverse('yakuza:save_user_ajax'), mismatch_payload)
        self.assertEqual(mismatch_response.status_code, 400)
        self.assertIn('must match', mismatch_response.json()['message'])
        self.assertFalse(User.objects.filter(username__in=[
            'short-password-user', 'mismatch-password-user',
        ]).exists())


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AdminPasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reset-target', password='OriginalPassword927')
        self.profile = UserProfile.objects.create(
            user=self.user,
            mobile_number='9876543210',
            role=UserProfile.RoleChoices.BRANCH_ADMIN,
            recovery_question=RECOVERY_QUESTIONS[0],
            recovery_answer_hash=make_password('bluebird'),
        )
        self.url = reverse('admin:auth_user_password_change', args=(self.user.pk,))

    def test_superuser_resets_password_and_preserves_account_data(self):
        administrator = User.objects.create_superuser(username='password-admin', password='AdminPassword927')
        self.client.force_login(administrator)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(self.url, {
            'password1': 'R8!pL2#vN6@xQ4$z',
            'password2': 'R8!pL2#vN6@xQ4$z',
        })
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.user.check_password('R8!pL2#vN6@xQ4$z'))
        self.assertEqual(self.user.pk, self.profile.user_id)
        self.assertEqual(self.profile.mobile_number, '9876543210')
        self.assertEqual(self.profile.recovery_question, RECOVERY_QUESTIONS[0])
        self.assertTrue(check_password('bluebird', self.profile.recovery_answer_hash))
        self.client.logout()
        self.assertTrue(self.client.login(username='reset-target', password='R8!pL2#vN6@xQ4$z'))

    def test_password_confirmation_and_policy_are_enforced(self):
        administrator = User.objects.create_superuser(username='password-admin', password='AdminPassword927')
        self.client.force_login(administrator)

        mismatch = self.client.post(self.url, {
            'password1': 'UpdatedPassword927!', 'password2': 'DifferentPassword927!',
        })
        self.assertEqual(mismatch.status_code, 200)
        self.assertFalse(User.objects.get(pk=self.user.pk).check_password('UpdatedPassword927!'))

        short = self.client.post(self.url, {'password1': 'abcde', 'password2': 'abcde'})
        self.assertEqual(short.status_code, 200)
        self.assertFalse(User.objects.get(pk=self.user.pk).check_password('abcde'))

    def test_staff_and_super_admin_role_cannot_reset_password(self):
        staff = User.objects.create_user(username='ordinary-staff', password='StaffPassword927', is_staff=True)
        permission = Permission.objects.get(content_type__app_label='auth', codename='change_user')
        staff.user_permissions.add(permission)
        UserProfile.objects.create(user=staff, role=UserProfile.RoleChoices.SUPER_ADMIN)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {
            'password1': 'UpdatedPassword927!', 'password2': 'UpdatedPassword927!',
        }).status_code, 403)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('OriginalPassword927'))


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class InAppPasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='app-reset-target', password='OriginalPassword927')
        self.profile = UserProfile.objects.create(
            user=self.user,
            mobile_number='9876543210',
            role=UserProfile.RoleChoices.SUPER_ADMIN,
            recovery_question=RECOVERY_QUESTIONS[0],
            recovery_answer_hash=make_password('bluebird'),
        )
        self.url = reverse('yakuza:reset_user_password', args=(self.user.pk,))

    def post_valid_password(self, client=None):
        return (client or self.client).post(self.url, {
            'new_password1': 'R8!pL2#vN6@xQ4$z',
            'new_password2': 'R8!pL2#vN6@xQ4$z',
        })

    def test_superuser_resets_password_and_preserves_account_data(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        self.client.force_login(administrator)

        response = self.post_valid_password()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        administrator.refresh_from_db()
        self.assertTrue(self.user.check_password('R8!pL2#vN6@xQ4$z'))
        self.assertTrue(administrator.check_password('AdminPassword927'))
        self.assertEqual(self.user.pk, self.profile.user_id)
        self.assertEqual(self.user.username, 'app-reset-target')
        self.assertEqual(self.profile.mobile_number, '9876543210')
        self.assertEqual(self.profile.recovery_question, RECOVERY_QUESTIONS[0])
        self.assertTrue(check_password('bluebird', self.profile.recovery_answer_hash))
        self.assertTrue(self.client.login(username='app-reset-target', password='R8!pL2#vN6@xQ4$z'))

        audit_entry = AuditLog.objects.get(module='User Management')
        self.assertEqual(audit_entry.user, administrator)
        self.assertIn('app-reset-target', audit_entry.action)
        self.assertNotIn('R8!pL2#vN6@xQ4$z', str(audit_entry.old_value) + str(audit_entry.new_value))

    def test_settings_user_management_shows_search_and_reset_action(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        branch_admin = User.objects.create_user(username='branch-admin-target', password='BranchPassword927')
        UserProfile.objects.create(user=branch_admin, role=UserProfile.RoleChoices.BRANCH_ADMIN)
        Settings.objects.create()
        InvoiceSetting.objects.create()
        self.client.force_login(administrator)

        response = self.client.get(reverse('yakuza:settings') + '#section-users')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Search accounts')
        self.assertContains(response, 'Reset Password')
        for target_id in (
            'u_password', 'u_confirm_password',
            'reset-user-password-new', 'reset-user-password-confirm',
        ):
            self.assertContains(response, f'data-target="{target_id}"')
        self.assertContains(response, reverse('yakuza:reset_user_password', args=(self.user.pk,)))
        self.assertContains(response, reverse('yakuza:reset_user_password', args=(administrator.pk,)))
        self.assertContains(response, reverse('yakuza:reset_user_password', args=(branch_admin.pk,)))
        self.assertNotContains(response, 'Cannot reset own password')
        page = response.content.decode()
        user_table = page[page.index('<table id="user-management-table"'):]
        user_table = user_table[:user_table.index('</table>')]
        self.assertLess(user_table.index('app-reset-target'), user_table.index('app-password-admin'))
        branch_admin_cell = user_table.index('<td>branch-admin-target</td>')
        branch_row_start = user_table.rfind('<tr class="user-row-branch-admin"', 0, branch_admin_cell)
        branch_row_end = user_table.index('</tr>', branch_row_start)
        branch_row = user_table[branch_row_start:branch_row_end]
        self.assertIn('btn-reset-user-password', branch_row)
        self.assertIn(reverse('yakuza:reset_user_password', args=(branch_admin.pk,)), branch_row)
        self.assertIn('<td class="user-status-cell">', branch_row)
        header = user_table[user_table.index('<thead>'):user_table.index('</thead>')]
        expected_headers = ['Name', 'Username', 'Role', 'Branch', 'Actions', 'Status']
        header_positions = [header.index(f'<th>{label}</th>') for label in expected_headers]
        self.assertEqual(header_positions, sorted(header_positions))
        self.assertIn('<td class="user-actions-cell">', user_table)
        self.assertIn('<td class="user-status-cell">', user_table)

    def test_actions_column_and_button_are_shown_for_every_row(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        branch_admin = User.objects.create_user(username='branch-admin-target', password='BranchPassword927')
        UserProfile.objects.create(user=branch_admin, role=UserProfile.RoleChoices.BRANCH_ADMIN)
        Settings.objects.create()
        InvoiceSetting.objects.create()
        self.client.force_login(administrator)

        response = self.client.get(reverse('yakuza:settings') + '#section-users')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        user_table = page[page.index('<table id="user-management-table"'):]
        user_table = user_table[:user_table.index('</table>')]
        self.assertIn('<th>Actions</th>', user_table)
        self.assertIn('<th>Status</th>', user_table)
        self.assertIn(reverse('yakuza:reset_user_password', args=(self.user.pk,)), user_table)
        self.assertIn(reverse('yakuza:reset_user_password', args=(administrator.pk,)), user_table)
        self.assertIn(reverse('yakuza:reset_user_password', args=(branch_admin.pk,)), user_table)
        self.assertEqual(user_table.count('btn-reset-user-password'), 3)
        branch_cell = user_table.index('<td>branch-admin-target</td>')
        branch_start = user_table.rfind('<tr class="user-row-branch-admin"', 0, branch_cell)
        branch_end = user_table.index('</tr>', branch_start)
        self.assertIn('btn-reset-user-password', user_table[branch_start:branch_end])

    def test_settings_shows_actions_heading_and_buttons_for_branch_admin_only_list(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        branch_admin = User.objects.create_user(username='branch-admin-target', password='BranchPassword927')
        UserProfile.objects.create(user=branch_admin, role=UserProfile.RoleChoices.BRANCH_ADMIN)
        Settings.objects.create()
        InvoiceSetting.objects.create()
        self.client.force_login(administrator)

        branch_admin_list = User.objects.filter(pk=branch_admin.pk)
        with patch.object(User.objects, 'select_related', return_value=branch_admin_list):
            response = self.client.get(reverse('yakuza:settings') + '#section-users')

        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        user_table = page[page.index('<table id="user-management-table"'):]
        user_table = user_table[:user_table.index('</table>')]
        self.assertNotIn('user-table-no-actions', user_table)
        self.assertIn('<th>Actions</th>', user_table)
        self.assertIn('<th>Status</th>', user_table)
        self.assertIn(reverse('yakuza:reset_user_password', args=(branch_admin.pk,)), user_table)
        self.assertIn('<td class="user-status-cell">', user_table)
        self.assertIn('btn-reset-user-password', user_table)

    def test_super_admin_can_reset_branch_admin_password_without_changing_own(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        branch_admin = User.objects.create_user(username='branch-admin-target', password='BranchPassword927')
        UserProfile.objects.create(user=branch_admin, role=UserProfile.RoleChoices.BRANCH_ADMIN)
        self.client.force_login(administrator)

        original_admin_password = administrator.password
        response = self.client.post(reverse('yakuza:reset_user_password', args=(branch_admin.pk,)), {
            'new_password1': 'UpdatedPassword927!',
            'new_password2': 'UpdatedPassword927!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        branch_admin.refresh_from_db()
        administrator.refresh_from_db()
        self.assertTrue(branch_admin.check_password('UpdatedPassword927!'))
        self.assertEqual(administrator.password, original_admin_password)

    def test_super_admin_can_reset_another_super_admin_account(self):
        administrator = User.objects.create_superuser(username='acting-admin', password='ActingPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        dell = User.objects.create_superuser(username='dell', password='DellsOldPassword927')
        UserProfile.objects.create(user=dell, role=UserProfile.RoleChoices.SUPER_ADMIN)
        self.client.force_login(administrator)
        original_admin_password = administrator.password

        response = self.client.post(reverse('yakuza:reset_user_password', args=(dell.pk,)), {
            'new_password1': 'DellsNewPassword927!',
            'new_password2': 'DellsNewPassword927!',
        })

        self.assertEqual(response.status_code, 200)
        dell.refresh_from_db()
        administrator.refresh_from_db()
        self.assertTrue(dell.check_password('DellsNewPassword927!'))
        self.assertEqual(administrator.password, original_admin_password)

    def test_superuser_can_reset_own_password_and_keep_session(self):
        administrator = User.objects.create_superuser(username='self-reset-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        Settings.objects.create()
        InvoiceSetting.objects.create()
        self.client.force_login(administrator)

        response = self.client.post(reverse('yakuza:reset_user_password', args=(administrator.pk,)), {
            'new_password1': 'N3w!AdminPassword927',
            'new_password2': 'N3w!AdminPassword927',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        administrator.refresh_from_db()
        self.assertTrue(administrator.check_password('N3w!AdminPassword927'))
        self.assertEqual(self.client.get(reverse('yakuza:settings')).status_code, 200)

    def test_reset_requires_matching_passwords_and_only_six_character_minimum(self):
        administrator = User.objects.create_superuser(username='app-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        self.client.force_login(administrator)

        mismatch = self.client.post(self.url, {
            'new_password1': 'UpdatedPassword927!', 'new_password2': 'DifferentPassword927!',
        })
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.json()['status'], 'error')
        self.assertFalse(User.objects.get(pk=self.user.pk).check_password('UpdatedPassword927!'))

        short = self.client.post(self.url, {'new_password1': 'abcde', 'new_password2': 'abcde'})
        self.assertEqual(short.status_code, 400)
        self.assertIn('at least 6 characters', short.json()['message'])
        self.assertFalse(User.objects.get(pk=self.user.pk).check_password('abcde'))

        six_character_password = self.client.post(self.url, {
            'new_password1': 'abcdef', 'new_password2': 'abcdef',
        })
        self.assertEqual(six_character_password.status_code, 200)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('abcdef'))

        simple_eight_character_password = self.client.post(self.url, {
            'new_password1': 'abcdefgh', 'new_password2': 'abcdefgh',
        })
        self.assertEqual(simple_eight_character_password.status_code, 200)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('abcdefgh'))

    def test_unauthenticated_request_is_rejected(self):
        response = self.post_valid_password()
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OriginalPassword927'))

    def test_application_super_admin_role_authorizes_reset_without_django_superuser_flag(self):
        administrator = User.objects.create_user(
            username='role-only-admin', password='AdminPassword927',
        )
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        self.client.force_login(administrator)

        response = self.post_valid_password()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('R8!pL2#vN6@xQ4$z'))

    def test_branch_admin_cannot_use_privileged_reset_functionality(self):
        branch_admin = User.objects.create_user(username='branch-role-admin', password='AdminPassword927')
        UserProfile.objects.create(user=branch_admin, role=UserProfile.RoleChoices.BRANCH_ADMIN)
        self.client.force_login(branch_admin)

        response = self.post_valid_password()
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('OriginalPassword927'))

    def test_reset_endpoint_requires_csrf(self):
        administrator = User.objects.create_superuser(username='csrf-password-admin', password='AdminPassword927')
        UserProfile.objects.create(user=administrator, role=UserProfile.RoleChoices.SUPER_ADMIN)
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(administrator)

        response = self.post_valid_password(csrf_client)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password('OriginalPassword927'))
