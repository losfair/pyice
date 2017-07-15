import application
import time

app = application.Application()

@app.route("/hello_world", methods = ["POST"])
def on_hello_world(ctx):
    print(ctx.request.headers.get("aaa"))
    print(ctx.request.form.get("bbb"))
    return "Hello world!"

@app.route("/hello_world_async", methods = ["POST"])
async def on_hello_world_async(ctx):
    print(ctx.request.form["ccc"])
    return "Hello world! (Async)"

@app.route("/current_time", methods = ["GET", "POST"])
async def on_current_time(ctx):
    return ctx.jsonify({
        "err": 0,
        "msg": "OK",
        "time": time.time()
    })

app.core.listen("127.0.0.1:1405")
