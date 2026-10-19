from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from yakuza.models import UserProfile
from yakuza.views import RECOVERY_QUESTIONS


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
            'new_password': '1234567', 'confirm_password': '1234567',
        })
        self.assertContains(response, 'at least 8 characters')
        response = self.client.post(reverse('yakuza:reset_password'), {
            'new_password': '12345678', 'confirm_password': '12345678',
        }, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse('yakuza:login'))
        self.assertContains(response, 'class="login-message-source"')
        self.assertContains(response, 'Your password has been reset. Please log in with your new password.')
        self.assertNotContains(response, 'role="status"')
        login_script = (Path(__file__).resolve().parent.parent / 'static' / 'js' / 'login.js').read_text(encoding='utf-8')
        self.assertIn('showToast(null, source.textContent.trim(), type, 3000', login_script)
        self.assertIn('duration = 3000', login_script)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('12345678'))
        self.assertFalse(self.user.check_password('Old!Password927'))
        self.assertNotEqual(self.user.password, 'New!SecurePass2026')
        old_login = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': 'Old!Password927',
        })
        self.assertEqual(old_login.status_code, 200)
        new_login = self.client.post(reverse('yakuza:login'), {
            'username': 'recovery-user', 'password': '12345678',
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
