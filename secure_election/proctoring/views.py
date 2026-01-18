import base64
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from users.models import Voter

import face_recognition
import numpy as np
from users.models import Voter
from django.contrib.auth.decorators import login_required


@login_required
def face_register(request):
    voter = Voter.objects.get(user=request.user)

    if request.method == "POST":
        image_data = request.POST.get('image')

        if image_data:
            format, imgstr = image_data.split(';base64,')
            voter.face_image.save(
                f"{voter.voter_id}.png",
                ContentFile(base64.b64decode(imgstr))
            )
            voter.save()

    return render(request, 'face_register.html')





@login_required
def face_authenticate(request):
    voter = Voter.objects.get(user=request.user)

    if request.method == "POST":
        image_data = request.POST.get('image')

        if not voter.face_image:
            return render(request, 'face_auth.html', {
                'error': 'No registered face found'
            })

        # Decode live image
        format, imgstr = image_data.split(';base64,')
        img_bytes = base64.b64decode(imgstr)

        with open('temp.png', 'wb') as f:
            f.write(img_bytes)

        # Load images
        registered_image = face_recognition.load_image_file(voter.face_image.path)
        live_image = face_recognition.load_image_file('temp.png')

        reg_enc = face_recognition.face_encodings(registered_image)
        live_enc = face_recognition.face_encodings(live_image)

        if reg_enc and live_enc:
            match = face_recognition.compare_faces(
                [reg_enc[0]], live_enc[0]
            )

            if match[0]:
                request.session['face_verified'] = True
                return redirect('/vote/')

        return render(request, 'face_auth.html', {
            'error': 'Face not matched'
        })

    return render(request, 'face_auth.html')
