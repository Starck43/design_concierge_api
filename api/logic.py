from django.core.files.storage import FileSystemStorage


class MediaFileStorage(FileSystemStorage):
	def save(self, name, content, max_length=None):
		if not self.exists(name):
			return super().save(name, content, max_length)
		else:
			# Prevent saving file on disk
			return name


def user_directory_path(instance, filename):
	directory_path = f'uploads/{instance.user.user_id}'
	return f'{directory_path}/{filename}'
