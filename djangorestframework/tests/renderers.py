from django.conf.urls.defaults import patterns, url
from django import http
from django.test import TestCase

from djangorestframework import status
from djangorestframework.views import View
from djangorestframework.compat import View as DjangoView
from djangorestframework.renderers import BaseRenderer, JSONRenderer, YAMLRenderer, \
    JSONPRenderer
from djangorestframework.parsers import JSONParser, YAMLParser
from djangorestframework.mixins import ResponseMixin
from djangorestframework.response import Response
from djangorestframework.utils.mediatypes import add_media_type_param

from StringIO import StringIO

DUMMYSTATUS = status.HTTP_200_OK
DUMMYCONTENT = 'dummycontent'

RENDERER_A_SERIALIZER = lambda x: 'Renderer A: %s' % x
RENDERER_B_SERIALIZER = lambda x: 'Renderer B: %s' % x

class RendererA(BaseRenderer):
    media_type = 'mock/renderera'
    format="formata"

    def render(self, obj=None, media_type=None):
        return RENDERER_A_SERIALIZER(obj)

class RendererB(BaseRenderer):
    media_type = 'mock/rendererb'
    format="formatb"

    def render(self, obj=None, media_type=None):
        return RENDERER_B_SERIALIZER(obj)

class MockView(ResponseMixin, DjangoView):
    renderers = (RendererA, RendererB)

    def get(self, request, **kwargs):
        response = Response(DUMMYSTATUS, DUMMYCONTENT)
        return self.render(response)
    
class MockGETView(View):
    def get(self, request, **kwargs):
        return {'foo':['bar','baz']}
    

urlpatterns = patterns('',
    url(r'^.*\.(?P<format>.+)$', MockView.as_view(renderers=[RendererA, RendererB])),
    url(r'^$', MockView.as_view(renderers=[RendererA, RendererB])),
    url(r'^jsonp/jsonrenderer$', MockGETView.as_view(renderers=[JSONRenderer, JSONPRenderer])),
    url(r'^jsonp/nojsonrenderer$', MockGETView.as_view(renderers=[JSONPRenderer])),
)


class RendererIntegrationTests(TestCase):
    """
    End-to-end testing of renderers using an RendererMixin on a generic view.
    """

    urls = 'djangorestframework.tests.renderers'

    def test_default_renderer_serializes_content(self):
        """If the Accept header is not set the default renderer should serialize the response."""
        resp = self.client.get('/')
        self.assertEquals(resp['Content-Type'], RendererA.media_type)
        self.assertEquals(resp.content, RENDERER_A_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_head_method_serializes_no_content(self):
        """No response must be included in HEAD requests."""
        resp = self.client.head('/')
        self.assertEquals(resp.status_code, DUMMYSTATUS)
        self.assertEquals(resp['Content-Type'], RendererA.media_type)
        self.assertEquals(resp.content, '')

    def test_default_renderer_serializes_content_on_accept_any(self):
        """If the Accept header is set to */* the default renderer should serialize the response."""
        resp = self.client.get('/', HTTP_ACCEPT='*/*')
        self.assertEquals(resp['Content-Type'], RendererA.media_type)
        self.assertEquals(resp.content, RENDERER_A_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_specified_renderer_serializes_content_default_case(self):
        """If the Accept header is set the specified renderer should serialize the response.
        (In this case we check that works for the default renderer)"""
        resp = self.client.get('/', HTTP_ACCEPT=RendererA.media_type)
        self.assertEquals(resp['Content-Type'], RendererA.media_type)
        self.assertEquals(resp.content, RENDERER_A_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_specified_renderer_serializes_content_non_default_case(self):
        """If the Accept header is set the specified renderer should serialize the response.
        (In this case we check that works for a non-default renderer)"""
        resp = self.client.get('/', HTTP_ACCEPT=RendererB.media_type)
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)
    
    def test_specified_renderer_serializes_content_on_accept_query(self):
        """The '_accept' query string should behave in the same way as the Accept header."""
        resp = self.client.get('/?_accept=%s' % RendererB.media_type)
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_unsatisfiable_accept_header_on_request_returns_406_status(self):
        """If the Accept header is unsatisfiable we should return a 406 Not Acceptable response."""
        resp = self.client.get('/', HTTP_ACCEPT='foo/bar')
        self.assertEquals(resp.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_specified_renderer_serializes_content_on_format_query(self):
        """If a 'format' query is specified, the renderer with the matching
        format attribute should serialize the response."""
        resp = self.client.get('/?format=%s' % RendererB.format)
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_specified_renderer_serializes_content_on_format_kwargs(self):
        """If a 'format' keyword arg is specified, the renderer with the matching
        format attribute should serialize the response."""
        resp = self.client.get('/something.formatb')
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_specified_renderer_is_used_on_format_query_with_matching_accept(self):
        """If both a 'format' query and a matching Accept header specified,
        the renderer with the matching format attribute should serialize the response."""
        resp = self.client.get('/?format=%s' % RendererB.format,
                               HTTP_ACCEPT=RendererB.media_type)
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_conflicting_format_query_and_accept_ignores_accept(self):
        """If a 'format' query is specified that does not match the Accept
        header, we should only honor the 'format' query string."""
        resp = self.client.get('/?format=%s' % RendererB.format,
                               HTTP_ACCEPT='dummy')
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

    def test_bla(self):
        resp = self.client.get('/?format=formatb',
            HTTP_ACCEPT='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        self.assertEquals(resp['Content-Type'], RendererB.media_type)
        self.assertEquals(resp.content, RENDERER_B_SERIALIZER(DUMMYCONTENT))
        self.assertEquals(resp.status_code, DUMMYSTATUS)

_flat_repr = '{"foo": ["bar", "baz"]}'

_indented_repr = """{
  "foo": [
    "bar", 
    "baz"
  ]
}"""


class JSONRendererTests(TestCase):
    """
    Tests specific to the JSON Renderer
    """

    def test_without_content_type_args(self):
        """
        Test basic JSON rendering.
        """
        obj = {'foo':['bar','baz']}
        renderer = JSONRenderer(None)
        content = renderer.render(obj, 'application/json')
        self.assertEquals(content, _flat_repr)

    def test_with_content_type_args(self):
        """
        Test JSON rendering with additional content type arguments supplied. 
        """
        obj = {'foo':['bar','baz']}
        renderer = JSONRenderer(None)
        content = renderer.render(obj, 'application/json; indent=2')
        self.assertEquals(content, _indented_repr)
    
    def test_render_and_parse(self):
        """
        Test rendering and then parsing returns the original object.
        IE obj -> render -> parse -> obj.
        """
        obj = {'foo':['bar','baz']}

        renderer = JSONRenderer(None)
        parser = JSONParser(None)

        content = renderer.render(obj, 'application/json')
        (data, files) = parser.parse(StringIO(content))
        self.assertEquals(obj, data)
        

class JSONPRendererTests(TestCase):
    """
    Tests specific to the JSONP Renderer
    """

    urls = 'djangorestframework.tests.renderers'

    def test_without_callback_with_json_renderer(self):
        """
        Test JSONP rendering with View JSON Renderer.
        """
        resp = self.client.get('/jsonp/jsonrenderer',
                               HTTP_ACCEPT='application/json-p')
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(resp['Content-Type'], 'application/json-p')
        self.assertEquals(resp.content, 'callback(%s);' % _flat_repr)
        
    def test_without_callback_without_json_renderer(self):
        """
        Test JSONP rendering without View JSON Renderer.
        """
        resp = self.client.get('/jsonp/nojsonrenderer',
                               HTTP_ACCEPT='application/json-p')
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(resp['Content-Type'], 'application/json-p')
        self.assertEquals(resp.content, 'callback(%s);' % _flat_repr)
        
    def test_with_callback(self):
        """
        Test JSONP rendering with callback function name.
        """
        callback_func = 'myjsonpcallback'
        resp = self.client.get('/jsonp/nojsonrenderer?callback='+callback_func,
                               HTTP_ACCEPT='application/json-p')
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(resp['Content-Type'], 'application/json-p')
        self.assertEquals(resp.content, '%s(%s);' % (callback_func, _flat_repr))


if YAMLRenderer:
    _yaml_repr = 'foo: [bar, baz]\n'
    
    
    class YAMLRendererTests(TestCase):
        """
        Tests specific to the JSON Renderer
        """
    
        def test_render(self):
            """
            Test basic YAML rendering.
            """
            obj = {'foo':['bar','baz']}
            renderer = YAMLRenderer(None)
            content = renderer.render(obj, 'application/yaml')
            self.assertEquals(content, _yaml_repr)
    
        
        def test_render_and_parse(self):
            """
            Test rendering and then parsing returns the original object.
            IE obj -> render -> parse -> obj.
            """
            obj = {'foo':['bar','baz']}
    
            renderer = YAMLRenderer(None)
            parser = YAMLParser(None)
    
            content = renderer.render(obj, 'application/yaml')
            (data, files) = parser.parse(StringIO(content))
            self.assertEquals(obj, data)    