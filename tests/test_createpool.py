from unittest import TestCase

from stellar_base.keypair import Keypair

from createpool import generate_pool_keypair

from mock import patch


class FakeKeyPair(object):

    def __init__(self, stub):
        self.stub = stub

    def address(self):
        return self.stub


class CreatePoolTestCase(TestCase):

    @patch.object(Keypair, 'random')
    def test_generate_pool_keypair(self, patched_random):
        patched_random.side_effect = map(
            FakeKeyPair, [b'1234-foo', b'1234-bar', b'1234-baz'])
        keypair = generate_pool_keypair()
        self.assertEqual(keypair.address(), b'1234-foo')

    @patch.object(Keypair, 'random')
    def test_generate_pool_keypair_with_tail(self, patched_random):
        patched_random.side_effect = map(
            FakeKeyPair, [b'1234-foo', b'1234-bar', b'1234-baz'])
        keypair = generate_pool_keypair('baz')
        self.assertEqual(keypair.address(), b'1234-baz')
