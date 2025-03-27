import multiprocessing
import threading
import os
from time import sleep
from flask import (
    Flask,
    make_response,
    request,
    send_file,
    redirect,
)

app_http = Flask("mock HTTP")
app_https = Flask("mock HTTPS")

script_directory = os.path.dirname(os.path.abspath(__file__))
pdf_valid_empty = script_directory + '/empty.pdf'
pdf_zerosize = script_directory + '/zerosize.pdf'
pdf_corrupt = script_directory + '/corrupt.pdf'
pdf_aes_enc = script_directory + '/aes_enc.pdf'

@app_http.route("/api/is_live")
def is_live():
    return "OK", 200


@app_http.route("/api/kill")
def kill():
    raise KeyboardInterrupt()
    return "OK", 200


@app_http.route("/api/get_empty")
def get_empty_pdf():
    return send_file(pdf_valid_empty, mimetype="application/pdf")



@app_http.route("/api/get_zerosize")
def get_zerosize_pdf():
    return send_file(pdf_zerosize, mimetype="application/pdf")


@app_http.route("/api/get_corrupted")
def get_corrupted_pdf():
    return send_file(pdf_corrupt, mimetype="application/pdf")


@app_http.route("/api/get_aes_encrypted")
def get_aes_encrypted_pdf():
    return send_file(pdf_aes_enc, mimetype="application/pdf")


# Simulate a server that requires a browser user-agent
@app_http.route("/api/needs_user_agent")
def needs_user_agent():
    if "User-Agent" in request.headers and "Mozilla" in request.headers["User-Agent"]:
        return get_empty_pdf()
    else:
        return make_response("Missing/bad user agent", 403)


@app_http.route("/api/redir_with_cookie_set")
def redir_set_cookie():
    response = redirect("/api/get_empty_needs_cookie")
    response.set_cookie("test_cookie", "cookie_val", max_age=3)
    return response


@app_http.route("/api/get_empty_needs_cookie")
def get_empty_needs_cookie():
    if not "test_cookie" in request.cookies:
        return make_response("forgot the cookie", 403)
    else:
        return get_empty_pdf()


@app_https.route("/api/ssl_is_live")
def is_live():
    return "OK", 200


@app_https.route("/api/ssl_get_empty")
def get_empty_pdf():
    return send_file(pdf_valid_empty, mimetype="application/pdf")


def start_https_server():
    app_https.run(debug=False, port=12334, ssl_context="adhoc", use_reloader=False)


if __name__ == "__main__":
    thr1 = multiprocessing.Process(target=start_https_server)
    thr1.start()
    
    app_http.run(debug=False, port=12333, use_reloader=False)
    
    thr1.terminate()
    thr1.join()
