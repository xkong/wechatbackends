#!/usr/bin/env python
# coding: utf-8
#
# xiaoyu <xiaokong1937@gmail.com>
#
# 2014/02/18
#
# WeChat(Weixin) backend
#
"""
Weixin Public Service Account backend.

With this tool, you can send app_msg or image_msg or text_msg or even publish
msg without open browser.

Requirments:
    requests
    django

See tests.py for example usage and for more details.
"""
import re
import urllib
import uuid
import random
import json

import requests

from django.contrib.sites.models import Site

__all__ = ['BaseClient', 'ClientLoginException']


class BaseClient(object):
    def __init__(self, email=None, password=None, weixin_id='', ticket=''):
        """
        Login to weixin server. If failed, raise ClientLoginException.
        Note: password should be md5 encryted. We don't encrypt raw pwd here.
        """
        if not email or not password:
            raise ValueError
        self.weixin_id = weixin_id
        self.ticket = ticket
        self.headers = {}
        self.cookies = ''

        self._set_opener()

        url_login = "https://mp.weixin.qq.com/cgi-bin/login"
        params = {'lang': 'zh_CN'}
        # Note: password is not the raw password! It's md5 encoded!
        # should look like `21232f297a57a5a743894a0e4a801fc3`
        data = {'username': email, 'pwd': password,
                'imgcode': '', 'f': 'json'}
        resp = requests.post(url_login, data=data,
                             params=params, headers=self.headers,
                             verify=False)
        self.cookies = resp.cookies
        resp = resp.json()

        if resp['base_resp']['ret'] not in (0, 65202):
            raise ClientLoginException
        self.token = resp['redirect_url'].split('=')[-1]

    def _set_opener(self):
        """
        Set request headers.
        """
        self.headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'https://mp.weixin.qq.com/',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'mp.weixin.qq.com',
            'Origin': 'mp.weixin.qq.com',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/'
                          '537.36 (KHTML, like Gecko) Chrome/30.0.1599.'
                          '101 Safari/537.36',
        }

    def _sendMsg(self, sendTo, data):
        """
        Send msg to specific users.
        """
        if sendTo == []:
            for _sendTo in sendTo:
                self._sendMsg(_sendTo, data)
            return

        referer = {
            'Referer': 'http://mp.weixin.qq.com/cgi-bin/singlemsgpage?'
                       'fromfakeid={0}&msgid=&source=&count=20&t=wxm-s'
                       'inglechat&lang=zh_CN'.format(sendTo)}

        self.headers.update(referer)

        body = {
            'error': 'false',
            'token': self.token,
            'tofakeid': sendTo,
            'ajax': 1}
        body.update(data)

        url = 'https://mp.weixin.qq.com/cgi-bin/singlesend'
        params = {
            't': 'ajax-response',
            'lang': 'zh_CN'
        }
        resp = self._request(url, data=body, params=params)

        return resp

    def _uploadImg(self, img_content):
        """
        Upload image to weixin server with image_content,
        image_content may come from image.read() or
        open('image.jpg', 'rb').read()
        """
        if not self.ticket or not self.weixin_id:
            pre_url = 'https://mp.weixin.qq.com/cgi-bin/appmsg'
            params = {
                'begin': '0',
                'count': '10',
                't': 'media/appmsg_list',
                'type': '10',
                'action': 'list',
                'token': self.token,
                'lang': 'zh_CN'
            }
            resp = requests.post(pre_url, verify=False, params=params,
                                 headers=self.headers, cookies=self.cookies)
            self.cookies = resp.cookies
            resp = resp.text
            ptn = 'ticket:"(.*?)",'
            self.ticket = re.findall(ptn, resp)[0]

            ptn = 'user_name:"(.*?)",'
            self.weixin_id = re.findall(ptn, resp)[0]

        file_name = '%s.jpg' % str(uuid.uuid4().hex[:16])
        content_type = 'application/octet-stream'

        files = {'file': (file_name, img_content, content_type)}

        data = {'Filename': file_name,
                'folder': '/cgi-bin/uploads',
                'Upload': 'Submit Query'}

        url = 'https://mp.weixin.qq.com/cgi-bin/filetransfer'
        params = {
            'action': 'upload_material',
            'lang': 'zh_CN',
            'f': 'json',
            'ticket_id': self.weixin_id,
            'ticket': self.ticket,
            'token': self.token,
        }

        resp = self._request(url, data=data, files=files, params=params)
        find_id = resp['content']
        return find_id

    def _delImg(self, file_id):
        """
        Delete image from weixin server with given file_id
        {"ret":"0", "msg":"ok"}
        """
        url = 'https://mp.weixin.qq.com/cgi-bin/modifyfile'
        data = {
            'fileid': file_id,
            'token': self.token,
            'lang': 'zh_CN',
            'random': str(random.random()),
            'f': 'json',
            'ajax': '1',
            'oper': 'del',
            't': 'ajax-response'
        }
        resp = self._request(url, data=data)
        return resp

    def _addAppMsg(self, articles):
        """
        Add App Msg with WeixinMps.
        Note: WeixinMp is a model of your weixin app.
        Weixinmp should have at least these fields.
            * title
            * content
            * digest
            * user(i.e weixin named as author)
            * fileid(cover image's fileid.)
            * cover_img(real cover image file shown on your server.)
            .....
        """
        body = {}
        data_head = {
            'AppMsgId': '',
            'count': len(articles),
        }
        body.update(data_head)
        for i in range(len(articles)):
            body.update(self._wrap_articles(i, articles[i]))

        data_tail = {
            'ajax': '1',
            'token': self.token,
            'lang': 'zh_CN',
            'random': str(random.random()),
            'f': 'json',
            't': 'ajax-response',
            'sub': 'create',
            'type': '10'
        }

        body.update(data_tail)

        url = 'https://mp.weixin.qq.com/cgi-bin/operate_appmsg'
        resp = self._request(url, data=body)
        return resp

    def _getAppMsgId(self):
        """
        Get latest app msg id.
        """
        params = {
            'action': 'list',
            'ajax'	: '1',
            'begin'	: '0',
            'count'	: '1',
            'f'	: 'json',
            'lang'	: 'zh_CN',
            'random': str(random.random()),
            'token'	: self.token,
            'type'	: '10',
        }

        url = 'https://mp.weixin.qq.com/cgi-bin/appmsg'

        resp = self._request(url, params=params)
        if resp['base_resp']['err_msg'] != 'ok':
            return ''
        app_msg_id = resp['app_msg_info']['item'][0]['app_id']
        return app_msg_id

    def _delAppMsg(self, app_msg_id):
        """
        Delete weixin app msg from weixin server by id.
        {"ret":"0", "msg":""}
        """
        data = {
            'ajax': '1',
            'AppMsgId': app_msg_id,
            'f': 'json',
            'lang': 'zh_CN',
            'random': str(random.random()),
            'sub': 'del',
            't': 'ajax-response',
            'token': self.token,
            'type': '10',
        }
        url = 'https://mp.weixin.qq.com/cgi-bin/operate_appmsg'
        resp = self._request(url, data=data)
        return resp

    def publish_msg(self, app_msg_id):
        '''
        Publish Daily App Msg
        {"msg":"msg..", "ret":"ret_code"}
        '''
        url = 'https://mp.weixin.qq.com/cgi-bin/masssendpage'
        params = {
            't': 'mass/send',
            'token': self.token,
            'lang': 'zh_CN'
        }
        referer = '%s?%s' % (url, urllib.urlencode(params))
        self.headers.update({'Referer': referer})

        url = 'https://mp.weixin.qq.com/cgi-bin/masssend'

        data = {
            'type': 10,
            'appmsgid': app_msg_id,
            'sex': 0,
            'groupid': '-1',
            'synctxweibo': 0,
            'synctxnews': 0,
            'country': '',
            'province': '',
            'city': '',
            'imgcode': '',
            'token': self.token,
            'lang': 'zh_CN',
            'random': str(random.random()),
            'f': 'json',
            'ajax': 1,
            't': 'ajax-response'
        }

        resp = self._request(url, data=data)
        return resp

    def _wrap_articles(self, idx, article):
        domain = Site.objects.get_current().domain
        url = article.get_absolute_url()
        sourceurl = 'http://%s%s' % (domain, url)
        if article.show_cover_pic:
            show = 1
        else:
            show = 0

        data = {
            'title%s' % idx: article.title,
            'content%s' % idx: article.content,
            'digest%s' % idx: article.digest,
            'author%s' % idx: article.user.username,
            'fileid%s' % idx: article.fileid,
            'show_cover_pic%s' % idx: show,
            'sourceurl%s' % idx: sourceurl,
        }

        return data

    def upload_app_content_img(self, img_content):
        '''
        Upload img for weixin article's content
        Note: upload images in weixin article's content
        Return {'url':'','state':'SUCCESS'}
        '''
        params = {
            'lang': 'zh_CN',
            't': 'ajax-editor-upload-img',
            'token': self.token,
        }
        base_url = 'https://mp.weixin.qq.com/cgi-bin/uploadimg2cdn'

        fake_filename = '%s.jpg' % str(uuid.uuid4().hex[:16])

        body = {
            'Filename': fake_filename,
            'param1': 'value1',
            'param2': 'value2',
            'fileName': fake_filename,
            'pictitle': fake_filename,
            'Upload': 'Submit Query',
        }

        content_type = 'application/octet-stream'

        files = {'upfile': (fake_filename, img_content, content_type)}
        resp = self._request(base_url, data=body, files=files, params=params)
        return resp

    def get_latest_fakeid(self):
        '''
        Bind openid and fakeid, we use openid to get the fakeid of a
        subscriber.
        Return {'base_resp': ..., 'msg_items': ''}
        '''
        params = {
            'lang': 'zh-CN',
            't': 'message/list',
            'count': 1,
            'day': 0,
            'filterivrmsg': 1,
            'token': self.token,
            'f': 'json'
        }
        url = 'https://mp.weixin.qq.com/cgi-bin/message'
        msg_items = self._request(url, params=params)['msg_items']
        resp = json.loads(msg_items)
        if len(resp['msg_item']) > 0:
            return resp['msg_item'][0]
        return ''

    def _request(self,
                 url=None,
                 method=None,
                 headers=None,
                 files=None,
                 data=None,
                 params=None,
                 auth=None,
                 cookies=None,
                 hooks=None,
                 verify=False):

        headers = self.headers if headers is None else headers
        cookies = self.cookies if cookies is None else cookies
        method = 'GET' if data is None else 'POST'

        # Proxy for requests, used for http_debug.
        # Note: by this way, you can use debug tool after its proxy set
        # to 192.168.1.122:8888 (like fiddler2 ).
        # Default: None.
        http_debug = False

        if http_debug:
            http_proxy = 'http://192.168.1.122:8888'
            https_proxy = 'http://192.168.1.122:8888'
            proxyDict = {'http': http_proxy,
                         'https': https_proxy}
        else:
            proxyDict = None

        if method == 'GET':
            resp = requests.get(url, params=params, headers=headers,
                                cookies=cookies, verify=verify,
                                proxies=proxyDict)
        else:
            resp = requests.post(url, params=params, data=data,
                                 headers=headers, cookies=cookies,
                                 verify=verify, files=files,
                                 proxies=proxyDict)
        self.cookies = cookies
        # FIXME: json decode error
        # On some circumstances, resp has no json data or so.
        # But I forgot what's happend here :(
        # @2014/06/02: still can remeber.
        return resp.json()


class ClientLoginException(Exception):
    pass
