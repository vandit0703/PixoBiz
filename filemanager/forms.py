from django import forms
from .models import Announcement, CalendarEvent
from .models import Profile
from django.contrib.auth.forms import PasswordChangeForm


class CalendarEventForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        label='Start Date & Time'
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        label='End Date & Time'
    )

    class Meta:
        model = CalendarEvent
        fields = ['title', 'event_type', 'start_date', 'end_date', 'remarks', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Event Title'
            }),
            'event_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional remarks (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            "requirement",
            "occasion",
            "side",
            "camera_requirement",
            "time",
            "start_date",
            "end_date",
            "state",
            "city",
            "caste",
            "visibility",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "time": forms.Select(attrs={"class": "form-select"}),
            "requirement": forms.Select(attrs={"class": "form-select"}),
            "occasion": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "caste": forms.TextInput(attrs={"class": "form-control"}),
            "side": forms.Select(attrs={"class": "form-select"}),
            "camera_requirement": forms.Select(attrs={"class": "form-select"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["bio", "phone", "company", "portfolio_url"]
        widgets = {
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "company": forms.TextInput(attrs={"class": "form-control"}),
            "portfolio_url": forms.URLInput(attrs={"class": "form-control"}),
        }


class SellerRequestForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["seller_message"]
        widgets = {
            "seller_message": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Tell us about your services"}),
        }

