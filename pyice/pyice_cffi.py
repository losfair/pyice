import cffi
import time
import threading
import asyncio

ffi = cffi.FFI()
ffi.cdef('''
typedef void * Resource;
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;

typedef void (*AsyncEndpointHandler) (int id, Resource call_info);
typedef Resource (*CallbackOnRequest) (const char *uri); // returns a Response

Resource ice_create_server();
Resource ice_server_listen(Resource handle, const char *addr);
Resource ice_server_router_add_endpoint(Resource handle, const char *p);
void ice_server_set_static_dir(Resource handle, const char *d);
void ice_server_set_session_cookie_name(Resource handle, const char *name);
void ice_server_set_session_timeout_ms(Resource handle, u64 t);
bool ice_server_add_template(Resource handle, const char *name, const char *content);
void ice_server_set_max_request_body_size(Resource handle, u32 size);

const char * ice_glue_request_get_remote_addr(Resource req);
const char * ice_glue_request_get_method(Resource req);
const char * ice_glue_request_get_uri(Resource req);
bool ice_glue_request_load_session(Resource req, const char *id);
void ice_glue_request_create_session(Resource req);
const char * ice_glue_request_get_session_id(Resource req);
const char * ice_glue_request_get_session_item(Resource req, const char *k);
void ice_glue_request_set_session_item(Resource req, const char *k, const char *v);
void ice_glue_request_remove_session_item(Resource req, const char *k);

const char * ice_glue_request_get_stats(Resource req);
void ice_glue_request_set_custom_stat(Resource req, const char *k, const char *v);

void ice_glue_request_add_header(Resource t, const char *k, const char *v);
const char * ice_glue_request_get_header(Resource t, const char *k);

const char * ice_glue_request_get_cookie(Resource t, const char *k);

Resource ice_glue_request_create_header_iterator(Resource t);
const char * ice_glue_request_header_iterator_next(Resource t, Resource itr_p);
void ice_glue_destroy_header_iterator(Resource itr_p);

void ice_glue_response_add_header(Resource t, const char *k, const char *v);
const char * ice_glue_response_get_header(Resource t, const char *k);
void ice_glue_response_set_cookie(Resource t, const char *k, const char *v, const char *options);

Resource ice_glue_create_response();
void ice_glue_response_set_body(Resource t, const u8 *body, u32 len);
const u8 * ice_glue_request_get_body(Resource t, u32 *len_out);
void ice_glue_response_set_file(Resource t, const char *path);

void ice_glue_response_set_status(Resource t, u16 status);

char * ice_glue_request_render_template_to_owned(Resource t, const char *name, const char *data);
bool ice_glue_response_consume_rendered_template(Resource t, char *output);

void ice_glue_register_async_endpoint_handler(AsyncEndpointHandler);

void ice_core_fire_callback(Resource call_info, Resource resp);
Resource ice_core_borrow_request_from_call_info(Resource call_info);
int ice_core_endpoint_get_id(Resource ep);

void ice_core_endpoint_set_flag(Resource ep, const char *name, bool value);
''')

lib = ffi.dlopen("libice_core.so")

class Ice:
    def __init__(self, session_timeout_ms = 600000):
        self.server = lib.ice_create_server()
        self.req_cb = ffi.callback("AsyncEndpointHandler", self.async_endpoint_handler)
        self.endpoint_dispatch_table = []
        self.listen_mode = "threaded"

        for i in range(65536):
            self.endpoint_dispatch_table.append(None)
        
        self.not_found = DispatchTarget(self, self.not_found_handler, blocking = True)

        lib.ice_glue_register_async_endpoint_handler(self.req_cb)
        lib.ice_server_set_session_timeout_ms(self.server, session_timeout_ms)
    
    def async_endpoint_handler(self, id, call_info):
        if id < 0 or self.endpoint_dispatch_table[id] == None:
            target = self.not_found
        else:
            target = self.endpoint_dispatch_table[id]
        
        target(call_info)

    def add_endpoint(self, path, handler = None, flags = [], blocking = False):
        if handler == None:
            raise Exception("handler required")
        ep = lib.ice_server_router_add_endpoint(self.server, path.encode())

        for f in flags:
            lib.ice_core_endpoint_set_flag(ep, f.encode(), True)

        ep_id = lib.ice_core_endpoint_get_id(ep)
        self.endpoint_dispatch_table[ep_id] = DispatchTarget(self, handler, blocking = blocking)
    
    def set_static_dir(self, dir):
        lib.ice_server_set_static_dir(self.server, dir.encode())
    
    def listen(self, addr):
        lib.ice_server_listen(self.server, addr.encode())

        self.ev_loop = asyncio.get_event_loop()
        self.ev_loop.run_forever()

    def run_endpoint(self, call_info, target):
        resp = Response.new()

        try:
            target(Request(lib.ice_core_borrow_request_from_call_info(call_info)), resp)
        except BaseException as e:
            print(e)
            resp.set_status(500)
            resp.set_body("Error: " + str(e) + "\n")

        lib.ice_core_fire_callback(call_info, resp.handle)
    
    async def run_endpoint_async(self, call_info, target):
        resp = Response.new()
        
        try:
            req = Request(lib.ice_core_borrow_request_from_call_info(call_info))
            await target(req, resp)
        except BaseException as e:
            print(e)
            resp.set_status(500)
            resp.set_body("Error: " + str(e) + "\n")

        lib.ice_core_fire_callback(call_info, resp.handle)
    
    def not_found_handler(self, req, resp):
        resp.set_status(404)
        resp.set_body("Not found\n")

class DispatchTarget:
    def __init__(self, server, handler, blocking = False):
        self.server = server
        self.handler = handler
        self.blocking = blocking
    
    def __call__(self, call_info):
        if self.blocking:
            self.server.run_endpoint(call_info, self.handler)
        elif asyncio.iscoroutinefunction(self.handler):
            self.server.ev_loop.call_soon_threadsafe(
                lambda: self.server.ev_loop.create_task(
                    self.server.run_endpoint_async(call_info, self.handler)
                )
            )
        else:
            t = threading.Thread(target = lambda: self.server.run_endpoint(call_info, self.handler))
            t.start()

class Request:
    def __init__(self, handle):
        self.handle = handle
    
    def get_header(self, k):
        try:
            return ffi.string(lib.ice_glue_request_get_header(self.handle, k.encode()))
        except:
            return None
        
    def get_cookie(self, k):
        try:
            return ffi.string(lib.ice_glue_request_get_cookie(self.handle, k.encode()))
        except:
            return None
    
    def get_remote_addr(self):
        return ffi.string(lib.ice_glue_request_get_remote_addr(self.handle))
    
    def get_uri(self):
        return ffi.string(lib.ice_glue_request_get_uri(self.handle))
    
    def get_method(self):
        return ffi.string(lib.ice_glue_request_get_method(self.handle))
    
    def get_body(self):
        body_len_p = ffi.new("u32 *")
        raw_data = lib.ice_glue_request_get_body(self.handle, body_len_p)

        body_len = int(body_len_p[0])
        if body_len == 0:
            return None

        return ffi.unpack(ffi.cast("const char *", raw_data), body_len)
    
    def get_session_item(self, k):
        try:
            return ffi.string(lib.ice_glue_request_get_session_item(self.handle, k.encode()))
        except:
            return None
    
    def set_session_item(self, k, v):
        lib.ice_glue_request_set_session_item(self.handle, k.encode(), v.encode())
    
    def remove_session_item(self, k):
        lib.ice_glue_request_remove_session_item(self.handle, k.encode())

class Response:
    def __init__(self, handle):
        self.handle = handle
    
    @staticmethod
    def new():
        return Response(lib.ice_glue_create_response())
    
    def add_header(self, k, v):
        lib.ice_glue_response_add_header(self.handle, k.encode(), v.encode())

    def set_body(self, data):
        if type(data) == str:
            data = data.encode()
        
        if type(data) != bytes:
            raise Exception("Invalid data")
        
        lib.ice_glue_response_set_body(self.handle, data, len(data))

    def set_status(self, status):
        if type(status) != int or status < 100 or status >= 600:
            raise Exception("Invalid status")
        lib.ice_glue_response_set_status(self.handle, status)
    
    def set_cookie(self, k, v):
        if type(k) != str or type(v) != str:
            raise Exception("Invalid key or value")
        
        lib.ice_glue_response_set_cookie(self.handle, k.encode(), v.encode(), "".encode())
