from functools import partial
from tornado import gen

from .redistest import RedisTestCase, async_test


class PubSubTestCase(RedisTestCase):

    def setUp(self):
        super(PubSubTestCase, self).setUp()
        self._message_count = 0
        self.publisher = self._new_client()

    def tearDown(self):
        try:
            self.publisher.connection.disconnect()
            del self.publisher
        except AttributeError:
            pass
        super(PubSubTestCase, self).tearDown()

    def pause(self, timeout, callback=None):
        self.delayed(timeout, callback)

    def _expect_messages(self, messages, subscribe_callback=None):
        self._expected_messages = messages
        self._subscribe_callback = subscribe_callback

    def _handle_message(self, msg):
        self._message_count += 1
        self.assertIn(msg.kind, self._expected_messages)
        expected = self._expected_messages[msg.kind]
        self.assertIn(msg.pattern, expected[0::2])
        if 'subscribe' not in msg.kind:
            self.assertIn(msg.body, expected[1::2])
        if msg.kind in ('subscribe', 'psubscribe'):
            if self._subscribe_callback:
                cb = self._subscribe_callback
                self._subscribe_callback = None
                cb(True)

    @async_test
    @gen.engine
    def test_pub_sub(self):
        self._expect_messages({'subscribe': ('foo', 1),
                               'message': ('foo', 'bar'),
                               'unsubscribe': ('foo', 0)},
                              subscribe_callback=(yield gen.Callback('sub')))
        yield gen.Task(self.client.subscribe, 'foo')
        self.client.listen(self._handle_message,
                           exit_callback=(yield gen.Callback('listen')))
        yield gen.Wait('sub')
        yield gen.Task(self.publisher.publish, 'foo', 'bar')
        yield gen.Task(self.publisher.publish, 'foo', 'bar')
        yield gen.Task(self.publisher.publish, 'foo', 'bar')
        yield gen.Task(self.client.unsubscribe, 'foo')
        yield gen.Wait('listen')

        self.assertEqual(self._message_count, 5)
        self.assertFalse(self.client.subscribed)
        self.stop()

    @async_test
    @gen.engine
    def test_unsubscribe(self):
        def on_message(*args, **kwargs):
            self._message_count += 1

        yield gen.Task(self.client.subscribe, 'foo')
        self.client.listen(on_message, (yield gen.Callback('listen')))
        self.assertTrue(self.client.subscribed)
        yield gen.Task(self.client.unsubscribe, 'foo')
        yield gen.Wait('listen')

        self.assertFalse(self.client.subscribed)
        yield gen.Task(self.client.subscribe, 'foo')
        self.client.listen(on_message, (yield gen.Callback('listen')))
        self.assertTrue(self.client.subscribed)
        yield gen.Task(self.client.unsubscribe, 'foo')
        yield gen.Wait('listen')

        self.assertFalse(self.client.subscribed)
        self.assertEqual(self._message_count, 4)
        self.stop()

    @async_test
    @gen.engine
    def test_pub_sub_multiple(self):
        self._expect_messages({'subscribe': ('foo', 1, 'boo', 2),
                               'message': ('foo', 'bar', 'boo', 'zar'),
                               'unsubscribe': ('foo', 0, 'boo', 0)},
                              subscribe_callback=(yield gen.Callback('sub')))
        yield gen.Task(self.client.subscribe, 'foo')
        self.client.listen(self._handle_message, (yield gen.Callback('listen')))
        yield gen.Wait('sub')
        yield gen.Task(self.client.subscribe, 'boo')
        yield gen.Task(self.publisher.publish, 'foo', 'bar')
        yield gen.Task(self.publisher.publish, 'boo', 'zar')

        yield gen.Task(self.client.unsubscribe, ['foo', 'boo'])
        yield gen.Wait('listen')

        self.assertEqual(self._message_count, 6)
        self.assertFalse(self.client.subscribed)
        self.stop()

    @async_test
    @gen.engine
    def test_pub_sub_multiple_2(self):
        self._expect_messages({'subscribe': ('foo', 1, 'boo', 2),
                               'message': ('foo', 'bar', 'boo', 'zar'),
                               'unsubscribe': ('foo', 0, 'boo', 0)},
                              subscribe_callback=(yield gen.Callback('sub')))

        yield gen.Task(self.client.subscribe, ['foo', 'boo'])
        self.client.listen(self._handle_message, (yield gen.Callback('listen')))
        yield gen.Wait('sub')

        yield gen.Task(self.publisher.publish, 'foo', 'bar')
        yield gen.Task(self.publisher.publish, 'boo', 'zar')

        yield gen.Task(self.client.unsubscribe, ['foo', 'boo'])
        yield gen.Wait('listen')

        self.assertEqual(self._message_count, 6)
        self.assertFalse(self.client.subscribed)
        self.stop()

    @async_test
    @gen.engine
    def test_pub_psub(self):
        self._expect_messages({'psubscribe': ('foo.*', 1),
                               'pmessage': ('foo.*', 'bar'),
                               'punsubscribe': ('foo.*', 0),
                               'unsubscribe': ('foo.*', 1)},
                              subscribe_callback=(yield gen.Callback('sub')))
        yield gen.Task(self.client.psubscribe, 'foo.*')
        self.client.listen(self._handle_message, (yield gen.Callback('listen')))
        yield gen.Wait('sub')
        yield gen.Task(self.publisher.publish, 'foo.1', 'bar')
        yield gen.Task(self.publisher.publish, 'bar.1', 'zar')
        yield gen.Task(self.client.punsubscribe, 'foo.*')

        yield gen.Wait('listen')

        self.assertEqual(self._message_count, 3)
        self.stop()
