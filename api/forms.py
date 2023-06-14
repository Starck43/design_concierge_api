from django import forms

from api.models import User, Category


class UserForm(forms.ModelForm):
	class Meta:
		model = User
		fields = '__all__'
		widgets = {
			'description': forms.Textarea(attrs={'rows': 3}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		instance = kwargs.get('instance', None)
		if instance:
			self.fields['categories'].queryset = Category.objects.filter(group__in=instance.groups.all())
