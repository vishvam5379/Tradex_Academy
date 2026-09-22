from django.db import migrations, models


def remove_demo_videos(apps, schema_editor):
    """
    Remove hardcoded/sample demo videos (BigBuckBunny, Sintel, etc.)
    previously seeded into the Video model.
    """
    Video = apps.get_model('courses', 'Video')
    WatchProgress = apps.get_model('courses', 'WatchProgress')
    # First delete watch progress records linked to demo videos to prevent FK errors
    WatchProgress.objects.all().delete()
    # Delete all demo videos
    Video.objects.all().delete()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_communitychannel_communitymessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lecture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('course', models.CharField(
                    choices=[
                        ('indian_market', 'Indian Market Mastery'),
                        ('forex_gold', 'Forex & Gold Mastery')
                    ],
                    help_text='Course to which this lecture belongs',
                    max_length=50
                )),
                ('position', models.PositiveIntegerField(
                    default=1,
                    help_text='Lecture order position in the course'
                )),
                ('video_path', models.CharField(
                    help_text="Storage path inside the private Supabase bucket (e.g. 'indian_market/lecture_1.mp4')",
                    max_length=500
                )),
                ('duration_seconds', models.PositiveIntegerField(
                    default=0,
                    help_text='Duration in seconds'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Lecture',
                'verbose_name_plural': 'Lectures',
                'ordering': ['course', 'position', 'id'],
            },
        ),
        migrations.RunPython(remove_demo_videos, reverse_noop),
    ]
