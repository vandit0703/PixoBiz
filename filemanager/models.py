from django.db import models
from django.contrib.auth.models import User
import uuid

class Folder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subfolders'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    folder = models.ForeignKey(
        Folder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="files"
    )
    file = models.FileField(upload_to="user_files/")
    thumbnail = models.ImageField(
        upload_to="user_files/thumbs/",
        null=True,
        blank=True
    )
    preview = models.ImageField(upload_to="previews/", null=True, blank=True)
    original_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    numeric_key = models.BigIntegerField(null=True, blank=True, db_index=True)
    file_type = models.CharField(
        max_length=20,
        null=True,
        choices=[
            ("image", "Image"),
            ("video", "Video"),
            ("file", "File"),
        ]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "folder"]),
            models.Index(fields=["uploaded_at"]),
            models.Index(fields=["numeric_key"]),
        ]

    def save(self, *args, **kwargs):
        # file size
        if self.file and hasattr(self.file, "size"):
            self.file_size = self.file.size

        # numeric sort key (last number)
        import re
        numbers = re.findall(r"(\d+)", self.original_name)
        self.numeric_key = int(numbers[-1]) if numbers else None

        # auto file type
        import mimetypes
        mime, _ = mimetypes.guess_type(self.file.name)
        if mime:
            if mime.startswith("image"):
                self.file_type = "image"
            elif mime.startswith("video"):
                self.file_type = "video"
            else:
                self.file_type = "file"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.original_name


class FolderShare(models.Model):
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        related_name="shared_links"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    allow_download = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.folder.name} ({self.token})"
    
class Plan(models.Model):
    """Simple subscription plan model for admin configuration"""
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    storage_limit_gb = models.IntegerField(default=10, help_text="Storage limit in GB")

    def __str__(self):
        return f"{self.name} — {self.storage_limit_gb} GB"

class FaceEmbedding(models.Model):
    """
    Stores extracted face embeddings for fast search
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.ForeignKey(UserFile, on_delete=models.CASCADE, related_name="faces")
    embedding = models.BinaryField()  # numpy array bytes
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Face - File ID {self.file.id}"
    
class PhotoAlbum(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    folder = models.OneToOneField(
        Folder,
        on_delete=models.CASCADE,
        related_name="photo_album"
    )

    album_name = models.CharField(max_length=255)
    event_date = models.DateField()

    allow_download = models.BooleanField(default=True)
    watermark = models.BooleanField(default=False)
    watermark_applied = models.BooleanField(default=False)
    watermark_logo = models.ImageField(upload_to="watermarks/", null=True, blank=True)
    watermark_position = models.CharField(max_length=5, null=True, blank=True)
    pin = models.CharField(max_length=4, blank=True, null=True)

    cover_image = models.ImageField(
        upload_to="album_covers/",
        blank=True,
        null=True
    )
    public_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        null=True,
        blank=True
    )
    download_mode = models.CharField(
        max_length=20,
        choices=[
            ("original", "Original"),
            ("watermark", "Watermark")
        ],
        default="original"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.album_name


class FaceSearchLog(models.Model):
    album = models.ForeignKey(PhotoAlbum, on_delete=models.CASCADE, related_name="face_logs")

    visitor_name = models.CharField(max_length=120)
    visitor_mobile = models.CharField(max_length=15)

    match_count = models.IntegerField(default=0)
    searched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.visitor_name} - {self.album.album_name}"

class Announcement(models.Model):
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("staff", "Staff Only"),
        ("owner", "Owner Only"),
    ]

    CAMERA_CHOICES = [
        ("camcoder", "Camcoder"),
        ("apsc", "APSC"),
        ("fullframe", "Full Frame"),
    ]

    SIDE_CHOICES = [
        ("bride", "Bride Side"),
        ("groom", "Groom Side"),
        ("both", "Both Sides"),
    ]

    REQUIREMENT_CHOICES = [
        ("regular video", "Regular Video"),
        ("regular photography", "Regular Photography"),
        ("cinematography", "Cinematography"),
        ("drone photography", "Drone Photography"),
        ("video editor", "Video Editor"),
        ("album designer", "Album Designer"),
        ("live", "Live"),
        ("vfx", "VFX"),
        ("animation 2d/3d", "Animation 2D/3D"),
        ("candid photography", "Candid Photography"),
        ("pre wedding shoot", "Pre Wedding Shoot"),
        ("engagement shoot", "Engagement Shoot"),
    ]
    TIME_CHoICES = [
        ("half day", "Half Day"),
        ("full day", "Full Day"),
        ("multiple days", "Multiple Days"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="announcements")
    requirement = models.CharField(max_length=50, choices=REQUIREMENT_CHOICES)
    occasion = models.CharField(max_length=150, blank=True)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES, blank=True)
    camera_requirement = models.CharField(max_length=10, choices=CAMERA_CHOICES, blank=True)
    time = models.CharField(max_length=15, choices=TIME_CHoICES, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    caste = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="public", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Announcement by {self.user.username} — {self.occasion} ({self.start_date} → {self.end_date})"

    def is_active(self):
        from django.utils import timezone
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date


class CalendarEvent(models.Model):
    EVENT_TYPE_CHOICES = (
        ('shoot', 'Shoot'),
        ('work', 'Work'),
        ('other', 'Other'),
    )

    title = models.CharField(max_length=200)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='work'
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    remarks = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calendar_events'
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.title} ({self.start_date.date()} → {self.end_date.date()})"


class Applicant(models.Model):
    """
    Stores applicants for announcements/job postings
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='applicants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='job_applications'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('announcement', 'user')
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.user.username} applied for {self.announcement.occasion}"


class Profile(models.Model):
    """Extended profile information for users"""
    SELLER_STATUS = [
        ("none", "None"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=200, blank=True)
    portfolio_url = models.URLField(blank=True)
    seller_status = models.CharField(max_length=20, choices=SELLER_STATUS, default="none")
    seller_message = models.TextField(blank=True)

    # Plan and storage
    plan = models.ForeignKey("Plan", null=True, blank=True, on_delete=models.SET_NULL)
    # bytes used by user
    storage_used = models.BigIntegerField(default=0, help_text="Total storage used (bytes)")

    def storage_limit_bytes(self):
        if self.plan:
            return int(self.plan.storage_limit_gb) * 1024 * 1024 * 1024
        return None

    def has_space_for(self, size_bytes):
        limit = self.storage_limit_bytes()
        if limit is None:
            return True
        return (self.storage_used + size_bytes) <= limit

    def __str__(self):
        return f"Profile - {self.user.username}"


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    from .models import Plan
    if created:
        # Assign free plan to new user
        free_plan, _ = Plan.objects.get_or_create(name="Free", defaults={"storage_limit_gb": 10, "price": 0})
        Profile.objects.create(user=instance, plan=free_plan)
    else:
        try:
            instance.profile.save()
        except Exception:
            Profile.objects.get_or_create(user=instance)
            
# Nightly deletion task for free users
from django_cron import CronJobBase, Schedule
from .models import Profile, UserFile

class DeleteFreeUserFilesCronJob(CronJobBase):
    RUN_AT_TIMES = ['00:30']  # 12:30 AM every night
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'filemanager.delete_free_user_files'

    def do(self):
        free_users = Profile.objects.filter(plan__name="Free")
        for profile in free_users:
            files = UserFile.objects.filter(user=profile.user)
            for f in files:
                f.file.delete(save=False)
                f.delete()


class UploadSession(models.Model):
    """Tracks a chunked upload session for assembling large files."""
    import uuid
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=1024, blank=True, null=True)
    total_size = models.BigIntegerField()
    total_chunks = models.IntegerField()
    received_chunks = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"UploadSession {self.id} — {self.filename}"


# Update storage usage when files are created or deleted
@receiver(post_save, sender=UserFile)
def update_storage_on_save(sender, instance, created, **kwargs):
    try:
        profile = instance.user.profile
    except Exception:
        return

    if created:
        profile.storage_used = (profile.storage_used or 0) + (instance.file_size or 0)
        profile.save()


@receiver(post_delete, sender=UserFile)
def update_storage_on_delete(sender, instance, **kwargs):
    try:
        profile = instance.user.profile
    except Exception:
        return

    profile.storage_used = max(0, (profile.storage_used or 0) - (instance.file_size or 0))
    profile.save()