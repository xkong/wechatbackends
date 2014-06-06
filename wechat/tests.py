#!/usr/bin/env python
# coding: utf-8
#
# xiaoyu <xiaokong1937@gmail.com>
#
# 2014/02/18
#
"""
Tests for wechat backends.

Put this file to your/app/, serialize a `test_all.json` which include a
model and its instances and run
`python manage.py tests yourapp.WeChatTestCase`

WeixinMp is a model for your weixin article,

e.g:

class WeixinMp(models.Model):
    title = models.CharField(verbose_name=_('title'), max_length=128,
                             unique=True)
    content = models.TextField(verbose_name=_('content'))
    digest = models.CharField(verbose_name=_('digest'),
                              max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, verbose_name=_('author'))
    fileid = models.CharField(verbose_name=_('fileid'), max_length=32)
    show_cover_pic = models.BooleanField(verbose_name=_('show cover image'),
                                         default=True)

    cover_img = models.ImageField(verbose_name=_('Cover Image'),
                                  upload_to=UPLOAD_PATH,
                                  blank=True,
                                  help_text=_('Cover Image for article, will '
                                              'be set to `uploads/cover.jpg`'
                                              ' if left blank.'))

    is_published = models.BooleanField(_('is_published'), default=False)
    sync = models.BooleanField(_('Sync'), default=True,
                               help_text=_('Synchronize to weixin server.'))

"""
from django.test import TestCase
from django.conf import settings

from .base import BaseClient

from yourapp.models import WeixinMp


class WeChatTestCase(TestCase):
    fixtures = ['test_all.json']

    def setUp(self):
        email = getattr(settings, 'WEIXIN_EMAIL')
        password = getattr(settings, 'WEIXIN_PASSWORD')
        weixin_id = getattr(settings, 'WEIXIN_ID')
        self.client = BaseClient(email, password, weixin_id)
        self.fake_user = '640000000'
        self.articles = list(WeixinMp.objects.filter(is_valid=True))[:4]

    def test_get_latest_fakeid(self):
        resp = self.client.get_latest_fakeid()
        self.assertEqual('fakeid' in resp, True)

    def test_send_msg(self):
        data = {
            'type': 1,
            'content': 'this is a test'
        }

        msg = self.client._sendMsg(self.fake_user, data)
        self.assertEqual(msg['base_resp']['err_msg'], 'ok')

    def test_send_img(self):
        img_content = open('demo.png', 'rb').read()
        file_id = self.client._uploadImg(img_content)
        data = {
            'type': 2,
            'content': '',
            'fid': file_id,
            'fileid': file_id,
        }
        msg = self.client._sendMsg(self.fake_user, data)
        self.assertEqual(msg['base_resp']['err_msg'], 'ok')

    def test_send_app_msg(self):
        self.client._addAppMsg(self.articles[:3])
        app_msg_id = self.client._getAppMsgId()
        data = {
            'type': 10,
            'fid': app_msg_id,
            'appmsgid': app_msg_id
        }

        ret_msg = self.client._sendMsg(self.fake_user, data)
        self.assertEqual(ret_msg['base_resp']['err_msg'], 'ok')

    def test_content_img_upload(self):
        img_content = open('demo.png', 'rb').read()
        msg = self.client.upload_app_content_img(img_content)
        self.assertEqual(msg['state'], 'SUCCESS')

    def test_add_app_msg(self):
        msg = self.client._addAppMsg(self.articles[-1:])
        self.assertEqual(msg['msg'], 'OK')

    def test_publish_app_msg(self):
        return
        # Note: this function can really publish an app_msg to all the
        # users! If you really want to do this, comment the previous
        # `return`.
        msg_id = self.client._getAppMsgId()
        msg = self.client.publish_msg(msg_id)
        self.assertEqual(msg['base_resp']['err_msg'], 'ok')
