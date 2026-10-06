from django import forms

from accounts.models import User


class UserAddForm(forms.ModelForm):
    """Admin form for creating OTP/passwordless users."""

    class Meta:
        model = User
        fields = (
            "phone",
            "full_name",
            "email",
            "is_active",
            "is_staff",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
            self.save_m2m()
        return user
