from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello, World!"


@app.route("/update_params")
def hello():
    return "Hello, World!"
