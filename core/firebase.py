import firebase_admin
from django.conf import settings
from firebase_admin import credentials


def get_firebase_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    if settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        return firebase_admin.initialize_app(cred)

    return firebase_admin.initialize_app()
