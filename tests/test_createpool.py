from unittest import TestCase
import json

from stellar_base.keypair import Keypair
from stellar_base.horizon import horizon_testnet

from createpool import (generate_pool_keypair, create_pool_account)

import responses
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


class CreatePoolAccountTestCase(TestCase):

    @responses.activate
    def test_create_pool_account(self):
        account_kp = Keypair.random()
        pool_kp = Keypair.random()

        # fixture for getting the account
        responses.add(
            responses.GET,
            'https://horizon-testnet.stellar.org/accounts/%s' % (
                account_kp.address().decode()),
            body=json.dumps({'sequence': '1234'}),
            content_type='application/json')

        # fixture for creating a transaction
        responses.add(
            responses.POST,
            'https://horizon-testnet.stellar.org/transactions/',
            body=json.dumps({
                '_links': {
                    'transaction': {
                        'href': 'http://transaction-url/'
                    }
                }
            }),
            content_type='application/json')

        self.assertTrue(create_pool_account(
            horizon_testnet(), 'TESTNET', account_kp.seed(), pool_kp))
