from django import forms

from api.models import User, Category


class UserForm(forms.ModelForm):
	class Meta:
		model = User
		fields = '__all__'
		widgets = {
			'description': forms.Textarea(attrs={'rows': 3}),
			'total_rating': forms.TextInput(attrs={'suffix': '️⭐', 'label': 'Рейтинг'}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
