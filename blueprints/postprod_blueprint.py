import os
import logging
from flask import Blueprint, request, render_template, current_app
from postprocessor import ProductionWav

postprod_bp = Blueprint("postprod", __name__, url_prefix="/prod")
logger = logging.getLogger(__name__)

@postprod_bp.route('/postprocess', methods=['POST'])
def postprocess():
    """
    Trigger post-production on a WAV file.
    Expects: filename, metadatafilename, intro, transition, outro (form fields or JSON)
    """
    try:
        # Get params from request
        filename = request.form.get("filename") or request.json.get("filename")
        metadatafilename = request.form.get("metadatafilename") or request.json.get("metadatafilename")
        intro = request.form.get("intro") or request.json.get("intro")
        transition = request.form.get("transition") or request.json.get("transition")
        outro = request.form.get("outro") or request.json.get("outro")

        if not filename:
            return render_template("error.html", title="ERROR", error="Missing filename"), 400

        # Resolve paths
        wav_path = os.path.join(current_app.config["AUDIO_FOLDER"], filename)
        if not os.path.exists(wav_path):
            return render_template("error.html", title="ERROR", error=f"WAV file not found: {wav_path}"), 404

        meta_path = None
        if metadatafilename:
            meta_path = os.path.join(current_app.config["PROCESSED_FOLDER"], metadatafilename)
            if not os.path.exists(meta_path):
                logger.warning(f"Metadata file not found: {meta_path}")

        # Build config
        config = {
            "intro": intro,
            "transition": transition,
            "outro": outro,
            "overlay_volume": -5  # default
        }

        # Run post-production
        processor = ProductionWav(wav_path, config)

        return render_template(
            "success.html",
            title="SUCCESS",
            message=f"Post-processed audio created for {filename}.",
            file=os.path.basename(processor._get_output_path())
        )

    except Exception as e:
        logger.exception("Post-processing failed")
        return render_template("error.html", title="ERROR", error=str(e)), 500
