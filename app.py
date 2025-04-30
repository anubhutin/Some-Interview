# from flask import Flask, render_template, request, redirect, url_for, send_file, flash, send_from_directory
# import os
# import json
# from LLM_Module.newtranscriber import VideoTranscriber
# from LLM_Module.Overall_Analyser import VideoResumeEvaluator
# from video_module.VideoEvaluation import VideoAnalyzer 
# from LLM_Module.Qualitative_Analyser import VideoResumeEvaluator2
# from report_generation_module.PDF_Generator import create_combined_pdf
# from video_module.drive_video_download import download_drive_url
# from LLM_Module.score_analyser import score_analyser
# os.environ['FLASK_RUN_EXTRA_FILES'] = ''

# app = Flask(__name__)
# app.secret_key = "your_secret_key_here"  # needed for flashing messages

# # Ensure required folders exist
# for folder in ["json", "reports", os.path.join("static", "uploads")]:
#     os.makedirs(os.path.join(app.root_path, folder), exist_ok=True)

# @app.route("/", methods=["GET", "POST"])
# def index():
#     if request.method == "POST":
#         user_name = request.form.get("user_name")
#         youtube_url = request.form.get("youtube_url")
#         video_file = request.files.get("video_file")
#         presentation_mode = request.form.get("presentation_mode")
        
#         print("<------------------------------------------------------->")
#         print("Presentation Mode : ", presentation_mode)
#         print("<------------------------------------------------------->")
        
#         # Save presentation mode info
#         with open("json/presentation.json", "w") as file:
#             json.dump({"presentation_mode": presentation_mode}, file, indent=4)

#         if not user_name:
#             flash("Name is required before uploading a video.", "warning")
#             return redirect(request.url)

#         try:
#             uploads_dir = os.path.join(app.root_path, "static", "uploads")
#             if youtube_url:
#                 download_drive_url(youtube_url)
#                 file_path = os.path.join(uploads_dir, "video.mp4")
#                 video_filename = "video.mp4"
#             else:
#                 if not video_file:
#                     flash("Video file is missing!", "warning")
#                     return redirect(request.url)
#                 file_path = os.path.join(uploads_dir, "video.mp4")
#                 video_file.save(file_path)
#                 video_filename = "video.mp4"

#             # Analyze the video
#             with open(file_path, 'rb') as f:
#                 analyzer = VideoAnalyzer(f)
#                 analysis_output = analyzer.analyze_video()

#             output_json_path = os.path.join(app.root_path, "json", "output.json")
#             with open(output_json_path, 'w', encoding='utf-8') as json_file:
#                 json.dump(analysis_output, json_file, ensure_ascii=False, indent=4)

#             # Transcribe the video audio
#             with open(file_path, 'rb') as f:
#                 audio_path = os.path.join(app.root_path, "audiofile.wav")
#                 transcription_json_path = os.path.join(app.root_path, "json", "transcription_output.json")
#                 transcriber = VideoTranscriber(f, audio_path, transcription_json_path)
#                 transcription_output = transcriber.transcribe()

#             evaluator = VideoResumeEvaluator()
#             quality_evaluator = VideoResumeEvaluator2() 

#             eval_results = evaluator.evaluate_transcription(transcription_output)
#             print("AI Results -->", eval_results)
#             output = score_analyser(eval_results)
#             with open(os.path.join(app.root_path, "json", "scores.json"), 'w') as fp:
#                 json.dump(output, fp)
#             quality_evaluator.evaluate_transcription(transcription_output)

#             # Update output JSON data with user's name and evaluation results
#             with open(output_json_path, 'r') as f:
#                 data = json.load(f)
#             data.update({
#                 'User Name': user_name,
#                 'LLM': eval_results
#             })
#             with open(output_json_path, 'w') as f:
#                 json.dump(data, f, indent=4)

#             # Generate a sanitized PDF filename with user's name
#             reports_dir = os.path.join(app.root_path, "reports")
#             pdf_filename = f"{user_name.strip().replace(' ', '_')}.pdf"
#             pdf_path = os.path.join(reports_dir, pdf_filename)
#             logo_path = os.path.join(app.root_path, "logos", "logo.png")
#             create_combined_pdf(logo_path, output_json_path, pdf_path)

#             flash("Video analysis and PDF report generation completed successfully!", "success")
#             return render_template("result.html", 
#                                    user_name=user_name, 
#                                    video_filename=video_filename, 
#                                    pdf_url=url_for("download_pdf", pdf_name=pdf_filename))
#         except Exception as e:
#             flash(f"An error occurred: {str(e)}", "danger")
#             return redirect(request.url)
#     return render_template("index.html")

# # Endpoint to serve uploaded video files
# @app.route('/uploads/<filename>')
# def uploaded_file(filename):
#     uploads = os.path.join(app.root_path, "static", "uploads")
#     return send_from_directory(uploads, filename)


# @app.route("/download_pdf/<pdf_name>")
# def download_pdf(pdf_name):
#     pdf_path = os.path.join(app.root_path, "reports", pdf_name)
#     return send_file(pdf_path, as_attachment=True, download_name=pdf_name)

# if __name__ == "__main__":
#     app.run(port='5032', host='0.0.0.0')
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, send_from_directory
import os
import json
import boto3
from LLM_Module.newtranscriber import VideoTranscriber
from LLM_Module.Overall_Analyser import VideoResumeEvaluator
from video_module.VideoEvaluations import VideoAnalyzer 
from LLM_Module.Qualitative_Analyser import VideoResumeEvaluator2
from report_generation_module.PDF_Generator import create_combined_pdf
from video_module.drive_video_download import download_drive_url
from LLM_Module.score_analyser import score_analyser
from datetime import datetime
from pymongo import MongoClient
from werkzeug.utils import secure_filename
os.environ['FLASK_RUN_EXTRA_FILES'] = ''

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # needed for flashing messages

# AWS S3 Configuration
S3_BUCKET = "some-prod2025"
S3_REGION = "ap-south-1"  # e.g., "us-east-1"
AWS_ACCESS_KEY = ""
AWS_SECRET_KEY = ""

# Initialize boto3 client with credentials
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# MongoDB connection setup
MONGO_URI = "mongodb://localhost:27017"  # or your actual URI
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["finalSomeResults"]
reports_collection = db["userData"]

# Ensure required folders exist
for folder in ["json", "reports", os.path.join("static", "uploads")]:
    os.makedirs(os.path.join(app.root_path, folder), exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_name = request.form.get("user_name")
        youtube_url = request.form.get("youtube_url")
        video_file = request.files.get("video_file")
        presentation_mode = request.form.get("presentation_mode")
        
        print("<------------------------------------------------------->")
        print("Presentation Mode : ", presentation_mode)
        print("<------------------------------------------------------->")
        
        # Save presentation mode info
        with open("json/presentation.json", "w") as file:
            json.dump({"presentation_mode": presentation_mode}, file, indent=4)

        if not user_name:
            flash("Name is required before uploading a video.", "warning")
            return redirect(request.url)

        try:
            uploads_dir = os.path.join(app.root_path, "static", "uploads")
            if youtube_url:
                download_drive_url(youtube_url)
                file_path = os.path.join(uploads_dir, "video.mp4")
                video_filename = "video.mp4"
            else:
                if not video_file:
                    flash("Video file is missing!", "warning")
                    return redirect(request.url)
                file_path = os.path.join(uploads_dir, "video.mp4")
                video_file.save(file_path)
                video_filename = "video.mp4"
            try:
                with open(file_path, "rb") as data:
                    s3_client.upload_fileobj(data, S3_BUCKET, f"videos/{secure_filename(user_name)}_video.mp4")
                print("Video uploaded successfully.")
            except Exception as e:
                print("Video upload failed:", e)

            # Analyze the video
            with open(file_path, 'rb') as f:
                analyzer = VideoAnalyzer(f)
                analysis_output = analyzer.analyze_video()

            output_json_path = os.path.join(app.root_path, "json", "output.json")
            with open(output_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(analysis_output, json_file, ensure_ascii=False, indent=4)

            # Transcribe the video audio
            with open(file_path, 'rb') as f:
                audio_path = os.path.join(app.root_path, "audio", "audiofile.wav")
                transcription_json_path = os.path.join(app.root_path, "json", "transcription_output.json")
                transcriber = VideoTranscriber(f, audio_path, transcription_json_path)
                transcription_output = transcriber.transcribe()
            
            print("AUDIO DONE")

            evaluator = VideoResumeEvaluator()
            quality_evaluator = VideoResumeEvaluator2() 

            eval_results = evaluator.evaluate_transcription(transcription_output)
            print("AI Results -->", eval_results)
            output = score_analyser(eval_results)
            with open(os.path.join(app.root_path, "json", "scores.json"), 'w') as fp:
                json.dump(output, fp)
            quality_evaluator.evaluate_transcription(transcription_output)

            # Update output JSON data with user's name and evaluation results
            with open(output_json_path, 'r') as f:
                data = json.load(f)
            data.update({
                'User Name': user_name,
                'LLM': eval_results
            })
            with open(output_json_path, 'w') as f:
                json.dump(data, f, indent=4)

            # Generate a sanitized PDF filename using the user's name
            reports_dir = os.path.join(app.root_path, "reports")
            pdf_filename = f"{user_name.strip().replace(' ', '_')}.pdf"
            pdf_path = os.path.join(reports_dir, pdf_filename)
            logo_path = os.path.join(app.root_path, "logos", "logo.png")
            create_combined_pdf(logo_path, output_json_path, pdf_path)

            try:
                with open(pdf_path, "rb") as data:
                    s3_client.upload_fileobj(data, S3_BUCKET, f"reports/{secure_filename(user_name)}_report.pdf")
                print("pdf uploaded successfully.")
            except Exception as e:
                print("Video upload failed:", e)
            # Upload PDF to S3

            video_s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/videos/{secure_filename(user_name)}_video.mp4"
            report_s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/reports/{secure_filename(user_name)}_report.pdf"

            # Prepare MongoDB document
            record = {
                "user_name": user_name,
                "video_url": video_s3_url,
                "report_url": report_s3_url,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Insert into MongoDB
            try:
                reports_collection.insert_one(record)
                print("Record inserted into MongoDB successfully.")
            except Exception as e:
                print("MongoDB insert failed:", e)

            flash("Video analysis and PDF report generation completed successfully!", "success")
            return render_template("result.html", 
                                   user_name=user_name, 
                                   video_filename=video_filename, 
                                   pdf_url=url_for("download_pdf", pdf_name=pdf_filename))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(request.url)
    return render_template("index.html")

# Endpoint to serve uploaded video files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    uploads = os.path.join(app.root_path, "static", "uploads")
    return send_from_directory(uploads, filename)

# Download endpoint that serves the PDF file with the provided filename
@app.route("/download_pdf/<pdf_name>")
def download_pdf(pdf_name):
    pdf_path = os.path.join(app.root_path, "reports", pdf_name)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_name)

if __name__ == "__main__":
    app.run(port='5032', host='0.0.0.0')
