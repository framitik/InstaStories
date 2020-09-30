from Instastories import start_scrape
from flask import Flask, render_template, jsonify, request, redirect
from flask_restful import Resource, Api
import os
import base64
import shutil
import settings
import logging
from thread_runner import ThreadRunner

app = Flask(__name__)
api = Api(app)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['DEBUG'] = True

SKIP_EXTENSIONS = (".json", ".txt")

settings.setup_logger()
logger = logging.getLogger(__name__)
user_settings = settings.get()

scraper_runner = ThreadRunner(start_scrape, user_settings["loop_delay_seconds"], user_settings["loop_variation_percentage"])

################### UTIL FUNCTIONS ###################
def get_log_file_list():
    scraping_logs_path = settings.get('scraping_log_file_path')
    if not os.path.exists(scraping_logs_path):
        return []
    with open(scraping_logs_path, "r+") as o:
        logs = [log_lines for log_lines in o.readlines()]
        return list(reversed(logs))

def get_folders(path, url):
    rendered_folders = []  # List of {type: 'folder', url: X, name: Y}
    if not os.path.exists(path): return []
    for folder in os.listdir(path):
        if folder.endswith(SKIP_EXTENSIONS): continue
        rendered_folders.append({'type': 'folder',
                                 'name': f"{folder}"})
    return {"folders": rendered_folders}

def get_media(path):
    to_render_media = []
    for media in os.listdir(path):
        if media.endswith(SKIP_EXTENSIONS): continue
        media_type = "img/png" if media.endswith(".jpg") else "video/mp4"
        content_tag = "img" if media_type == "img/png" else "video"
        with open(os.path.join(path, media), "rb") as media_element:
            base64_media = base64.b64encode(media_element.read()).decode("utf-8")
        to_render_media.append({'type': 'media', 'content_tag': content_tag, 'media_type': media_type, 'data': base64_media})
    return {"media": to_render_media}

################### ROUTES ###################

@app.route("/", methods=['GET', 'POST'], defaults={"loop_mode": False, "media_mode": "all", "ids_source": "all"})
def index(loop_mode, media_mode, ids_source):
    logger.info(f"{request.method} request to /index")
    is_user_logged_in = settings.has_setting("session_id")
    user_settings = settings.get()
    if request.method == "POST" and is_user_logged_in:
        user_limit = int(request.form["user_limit"]) if request.form["user_limit"].isdecimal() else -1
        media_mode, ids_source, loop_mode, status_button = request.form["mode_dropdown"], request.form["ids_dropdown"], request.form["loop_dropdown"], request.form["controlBtn"]
        scraper_runner_args = {"scrape_settings": user_settings, "user_limit": user_limit,
                               "media_mode": media_mode, "ids_source": ids_source}
        if status_button == "start":
            loop_mode = loop_mode == "True"
            scraper_runner.updateFuncArg(**scraper_runner_args).startFunction(keep_running=loop_mode)
        elif status_button == "stop": scraper_runner.stopFunction()
        elif status_button == "update": scraper_runner.updateFuncArg(**scraper_runner_args)
    logged_in_error = request.method == "POST" and not is_user_logged_in

    log_lines = get_log_file_list()
    return render_template('index.html',
                           log_lines=log_lines,
                           disclaimer={"logged_in_error": logged_in_error},
                           output=scraper_runner.getOutput(),
                           checkbox={"loop_mode": loop_mode, "media_mode": media_mode, "ids_source": ids_source},
                           status=scraper_runner.getStatus())

@app.route("/settings/", methods=['GET', 'POST'])
def settings_page():
    logger.info(f"{request.method} request to /settings")
    user_settings = settings.get()
    if not settings.has_setting("session_id"):
        return redirect("/login")  # Prompt the user to log-in if he's not
        logger.info("User not logged in, redirected to /login")
    if request.method == "POST":  # User is updating settings.
        for setting_name in request.form:
            if setting_name == "extra_ids":
                extra_ids = request.form["extra_ids"].splitlines()
                user_settings["extra_ids"] = extra_ids
            elif setting_name in ["loop_delay_seconds", "loop_variation_percentage"] and len(request.form[setting_name]) != 0:
                user_settings[setting_name] = int(request.form[setting_name])
            elif len(request.form[setting_name]) != 0:  # Updates other non-null settings.
                user_settings[setting_name] = request.form[setting_name]
        settings.update_settings_file(user_settings)
        logger.info("Updated settings")
    folder_path = user_settings["folder_path"]
    loop_args = {"loop_delay_seconds": user_settings["loop_delay_seconds"],
                 "loop_variation_percentage": user_settings["loop_variation_percentage"]}
    extra_ids = user_settings["extra_ids"]
    if request.method == "POST": scraper_runner.updateDelay(**loop_args)
    return render_template("settings.html", settings={"extra_ids": extra_ids, "folder_path": folder_path, **loop_args})

@app.route("/login/", methods=['GET', 'POST'])
def login_page():
    logger.info(f"{request.method} request to /login")
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        settings.update("session_id", f"sessionid={request.form['session_id']}")
        return redirect("/settings/")

@app.route("/settings/logout")
def logout():
    logger.info(f"{request.method} request to /settings/logout")
    settings.clear_setting("session_id")
    logger.info("The user has logged out")
    return render_template("login.html", disclaimer={"login_error": False})

@app.route("/settings/delete-media")
def delete_media_folder_if_present():
    logger.info(f"{request.method} request to /settings/delete-media")
    folder_path = settings.get("folder_path")
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        logger.info(f"Deleted {folder_path} folder")

@app.route("/gallery/", methods=['GET'], defaults={"username": None, "date": None})
@app.route("/gallery/<username>/", methods=['GET'], defaults={"date": None})
@app.route("/gallery/<username>/<date>/", methods=['GET'])
def gallery(username, date):
    logger.info(f"GET request to /gallery/{username if username else ''}{'/' + date if date else ''}")
    return render_template("gallery.html")

################### API ###################

class GetMedia(Resource):
    def get(self):
        user = request.args.get('user')
        date = request.args.get('date')
        folder_path = settings.get("folder_path")
        # From most to least specific
        if date:
            date_path = os.path.join(os.path.join(folder_path, user), date)
            to_render_items = get_media(date_path)
        elif user:
            user_path = os.path.join(folder_path, user)
            to_render_items = get_folders(user_path, request.url)
        else:
            to_render_items = get_folders(folder_path, request.url)
        return jsonify(to_render_items)


api.add_resource(GetMedia, '/api/media/')
################### RUN ###################


if __name__ == "__main__":
    app.run(debug=True, port=80, host='0.0.0.0')
