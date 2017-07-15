from . import pyice_cffi as pyice
import json
import asyncio
import urllib.parse
import http.cookies

class Application:
    def __init__(self):
        self.core = pyice.Ice()
    
    def route(self, path, methods = ["GET"]):
        def decorator(func):
            def check_method(req):
                if not req.get_method().decode() in methods:
                    raise Exception("Method not allowed")

            def wrapper(req, resp):
                check_method(req)
                ctx = Context(func, req, resp)
                return ctx.run()
            
            async def async_wrapper(req, resp):
                check_method(req)
                ctx = Context(func, req, resp)
                return await ctx.run_async()
            
            flags = []
            if "POST" in methods:
                flags.append("read_body")
            
            if asyncio.iscoroutinefunction(func):
                handler = async_wrapper
            else:
                handler = wrapper

            self.core.add_endpoint(path, handler = handler, flags = flags)
            return handler
        
        return decorator

class Context:
    def __init__(self, func, req, resp):
        self.func = func
        self.request = Request(req)
        self._resp = resp
    
    def set_response(self, src):
        body = src.get_body()
        if body != None:
            self._resp.set_body(body)

        c = src.marshal_cookies()
        if c != None and len(c) > 0:
            self._resp.add_header("Set-Cookie", c)
        
        for k in src.headers:
            self._resp.add_header(k, src.headers[k])
    
    def run(self):
        r = self.func(self)
        if type(r) == str or type(r) == bytes:
            r = Response(r)
        if isinstance(r, Response) == False:
            raise Exception("Return value of the view function is not a Response.")
        self.set_response(r)
    
    async def run_async(self):
        r = await self.func(self)
        if type(r) == str or type(r) == bytes:
            r = Response(r)
        if isinstance(r, Response) == False:
            raise Exception("Return value of the view function is not a Response.")
        self.set_response(r)
    
    def jsonify(self, data):
        return Response(json.dumps(data))

class Request:
    def __init__(self, under):
        self.raw_args = None
        self.raw_form = None
        self.raw_cookies = None
        self.under = under
        self.headers = RequestKV(self.under.get_header)
        self.form = RequestKV(self.get_form_item)
        self.cookies = RequestKV(self.get_cookie_item)
        self.args = RequestKV(self.get_arg)
    
    def json(self):
        return json.loads(self.under.get_body())

    def get_form_item(self, k):
        if self.raw_form == None:
            raw_body = self.under.get_body()
            if raw_body == None:
                self.raw_form = {}
            else:
                self.raw_form = urllib.parse.parse_qs(self.under.get_body().decode())
                for k in self.raw_form:
                    self.raw_form[k] = self.raw_form[k][0]
        return self.raw_form.get(k)
    
    def get_cookie_item(self, k):
        if self.raw_cookies == None:
            raw_cookies_str = self.under.get_header("Cookie").decode()
            if raw_cookies_str == None or len(raw_cookies_str) == 0:
                self.raw_cookies = {}
            else:
                self.raw_cookies = http.cookies.SimpleCookie()
                self.raw_cookies.load(raw_cookies_str)
        
        v = self.raw_cookies.get(k)
        if v == None:
            return None
        else:
            return v.value
    
    def get_arg(self, k):
        if self.raw_args == None:
            p = self.under.get_uri().decode()
            if p == None or len(p) == 0:
                self.raw_args = {}
            else:
                p = p.split("?")
                if len(p) < 2:
                    self.raw_args = {}
                else:
                    self.raw_args = urllib.parse.parse_qs(p[1])
                    for k in self.raw_args:
                        self.raw_args[k] = self.raw_args[k][0]
        
        return self.raw_args.get(k)

class RequestKV:
    def __init__(self, getter):
        self.getter = getter

    def get(self, key, default = None):
        if type(key) != str:
            raise TypeError("Key must be a str")
        
        ret = self.getter(key)
        if ret == None or ret == "" or ret == b"":
            return default
        
        return ret
    
    def __getitem__(self, key):
        ret = self.get(key)
        if ret == None:
            raise KeyError(key)
        return ret

class Response:
    def __init__(self, body = None):
        self.body = body
        self.cookies = {}
        self.headers = {}
    
    def get_body(self):
        return self.body
    
    def set_cookie(self, k, v):
        self.cookies[k] = v
    
    def marshal_cookies(self):
        c = http.cookies.SimpleCookie()
        for k in self.cookies:
            c[k] = self.cookies[k]
            c[k]["path"] = "/"
        return c.output(header = "").strip()
    
    def set_body(self, data):
        self.body = data
    
    def add_header(self, k, v):
        self.headers[k] = v
    
    def set_header(self, k, v):
        self.add_header(k, v)
