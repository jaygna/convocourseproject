from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import uuid
import logging
from io import BytesIO

import google.generativeai as genai
from google.cloud import texttospeech

# Configuration
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual API key
genai.configure(api_key="AIzaSyDqNk7-WH2NoPP3jDMB6s5eO5KqxMUgkCg")  


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files or 'audio' not in request.files:
        return jsonify({'error': 'Missing files'}), 400

    pdf_file = request.files['pdf']
    audio_file = request.files['audio']

    if pdf_file.filename == '' or audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Save files securely
        pdf_filename = secure_filename(str(uuid.uuid4()) + '_' + pdf_file.filename)
        audio_filename = secure_filename(str(uuid.uuid4()) + '_' + audio_file.filename)
        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)

        pdf_file.save(pdf_path)
        audio_file.save(audio_path)

        # Load Gemini multimodal model
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Prepare content: PDF, Audio, Prompt
        prompt_parts = [
            {
                "mime_type": "application/pdf",
                "data": open(pdf_path, "rb").read()
            },
            {
                "mime_type": "audio/wav",
                "data": open(audio_path, "rb").read()
            },
            "Answer the user's question about the uploaded book."
        ]

        # Generate response
        response = model.generate_content(prompt_parts)
        answer_text = response.text.strip()
        logger.info(f"Gemini response: {answer_text}")

        # Save the response to a .txt file
        response_text_file = os.path.join(UPLOAD_FOLDER, audio_filename + '_response.txt')
        with open(response_text_file, 'w') as f:
            f.write(answer_text)

        # Use Google Cloud TTS to generate audio
        tts_client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=answer_text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        tts_response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Save the TTS audio file (in memory)
        audio_output = BytesIO(tts_response.audio_content)
        audio_output.seek(0)  # Important: Reset the buffer to the beginning

        return send_file(audio_output, mimetype='audio/mpeg', download_name='response.mp3')

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
