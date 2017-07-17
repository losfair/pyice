import pyice
import time

app = pyice.application.Application()

@app.route("/hello_world", methods = ["GET", "POST"])
def on_hello_world(ctx):
    #ctx.request.load_session()
    resp = pyice.application.Response("Hello world!")
    resp.set_header("Content-Type", "text/plain; charset=utf-8")
    return resp

@app.route("/hello_world_async", methods = ["GET", "POST"])
async def on_hello_world_async(ctx):
    #ctx.request.load_session()
    resp = pyice.application.Response("Hello world! (Async)")
    resp.set_header("Content-Type", "text/plain; charset=utf-8")
    return resp

@app.route("/hello_world_blocking", methods = ["GET", "POST"], blocking = True)
def on_hello_world_blocking(ctx):
    resp = pyice.application.Response("Hello world! (Blocking)")
    resp.set_header("Content-Type", "text/plain; charset=utf-8")
    return resp

@app.route("/redirect_to_google", blocking = True)
def on_redirect_to_google(ctx):
    return ctx.redirect("https://www.google.com")

@app.route("/current_time", methods = ["GET", "POST"])
async def on_current_time(ctx):
    return ctx.jsonify({
        "err": 0,
        "msg": "OK",
        "time": time.time()
    })

@app.route("/cookies", methods = ["GET"])
async def on_cookies(ctx):
    k = "test_cookie"

    resp = pyice.application.Response(str(ctx.request.cookies.get(k)))
    resp.set_cookie(k, str(time.time()))

    return resp

app.core.listen("127.0.0.1:1405")
