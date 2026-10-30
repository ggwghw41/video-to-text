
import os
import uuid
import whisper

from flask import (
    Flask, render_template, request,
    send_from_directory, flash, redirect, url_for
)
from werkzeug.utils import secure_filename

# =========================
# CẤU HÌNH
# =========================

app = Flask(__name__)
app.secret_key = "video-to-text-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

# Đường dẫn FFmpeg trên máy tính
FFMPEG_BIN = (
    r"C:\Users\nguye\Downloads"
    r"\ffmpeg-9.0.2-essentials_build\bin"
)

os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ["PATH"]

ALLOWED_EXTENSIONS = {
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "mpeg", "mpg"
}

# Bộ nhớ lưu model đã tải
models = {}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_model(model_name):
    if model_name not in models:
        models[model_name] = whisper.load_model(model_name)
    return models[model_name]


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)

    return (
        f"{hours:02d}:{minutes:02d}:"
        f"{secs:02d},{milliseconds:03d}"
    )


def create_srt(segments):
    content = []

    for index, segment in enumerate(segments, start=1):
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        text = segment["text"].strip()

        content.append(
            f"{index}\n{start} --> {end}\n{text}\n"
        )

    return "\n".join(content)


# =========================
# TRANG CHỦ
# =========================

@app.route("/")
def index():
    return render_template("./index.html")

@app.route("/templates/<path:filename>")
def templates(filename):
    return send_from_directory(
        os.path.join(BASE_DIR, "templates"),
        filename
    )
# =========================
# XỬ LÝ VIDEO
# =========================

@app.route("/transcribe", methods=["POST"])
def transcribe():

    if "video" not in request.files:
        flash("Vui lòng chọn video!")
        return redirect(url_for("index"))

    video = request.files["video"]

    if video.filename == "":
        flash("Bạn chưa chọn video!")
        return redirect(url_for("index"))

    if not allowed_file(video.filename):
        flash("Định dạng video không được hỗ trợ!")
        return redirect(url_for("index"))

    model_name = request.form.get("model", "base")
    language = request.form.get("language", "vi")

    if model_name not in ["tiny", "base", "small", "medium"]:
        model_name = "base"

    if language not in ["vi", "en", "auto"]:
        language = "vi"

    unique_id = uuid.uuid4().hex

    original_name = secure_filename(video.filename)
    extension = original_name.rsplit(".", 1)[1].lower()

    video_path = os.path.join(
        UPLOAD_FOLDER,
        f"{unique_id}.{extension}"
    )

    txt_name = f"{unique_id}.txt"
    srt_name = f"{unique_id}.srt"

    try:
        # Lưu video
        video.save(video_path)

        # Tải model
        model = get_model(model_name)

        # Nhận diện giọng nói
        options = {
            "task": "transcribe",
            "fp16": False,
            "verbose": False
        }

        if language != "auto":
            options["language"] = language

        result = model.transcribe(video_path, **options)

        full_text = result["text"].strip()
        segments = result["segments"]

        # Lưu file TXT
        txt_path = os.path.join(OUTPUT_FOLDER, txt_name)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        # Lưu file SRT
        srt_path = os.path.join(OUTPUT_FOLDER, srt_name)

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(create_srt(segments))

        return render_template(
            "index.html",
            result=full_text,
            segments=segments,
            txt_name=txt_name,
            srt_name=srt_name,
            video_name=original_name
        )

    except Exception as e:
        app.logger.exception("Lỗi xử lý video")
        flash(f"Không thể xử lý video: {str(e)}")
        return redirect(url_for("index"))

    finally:
        # Xóa video sau khi xử lý
        if os.path.exists(video_path):
            os.remove(video_path)


# =========================
# TẢI FILE KẾT QUẢ
# =========================

@app.route("/download/<filename>")
def download(filename):
    if filename not in os.listdir(OUTPUT_FOLDER):
        flash("Không tìm thấy file!")
        return redirect(url_for("index"))

    return send_from_directory(
        OUTPUT_FOLDER,
        filename,
        as_attachment=True
    )


# =========================
# CHẠY SERVER
# =========================

if __name__ == "__main__":
    print("================================")
    print("VIDEO TO TEXT")
    print("Truy cập: http://127.0.0.1:5000")
    print("================================")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )