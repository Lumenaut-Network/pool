from unittest import TestCase
import os
import tempfile
import json

from stellar_base.keypair import Keypair
from stellar_base.horizon import horizon_testnet

from createpool import (
    generate_pool_keypair, create_pool_account,
    get_signers, set_account_signers, SIGNING_THRESHOLD)

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


class SetAccountSigners(TestCase):

    def mock_signers_file(self, signers):
        signers_file = tempfile.NamedTemporaryFile(delete=False)
        for signer in signers:
            signers_file.write(b'%s\n' % (signer.address(),))
        signers_file.close()
        self.addCleanup(os.remove, signers_file.name)
        return signers_file

    def test_get_signers(self):
        signers_file = self.mock_signers_file([
            FakeKeyPair(b'foo'),
            FakeKeyPair(b'bar'),
            FakeKeyPair(b'baz'),
        ])
        signers = get_signers(signers_file.name)
        self.assertEqual(signers, ['foo', 'bar', 'baz'])

    @responses.activate
    def test_set_account_signers(self):
        pool_kp = Keypair.random()
        signer1 = Keypair.random()
        signer2 = Keypair.random()

        # fixture for getting the account
        responses.add(
            responses.GET,
            'https://horizon-testnet.stellar.org/accounts/%s' % (
                pool_kp.address().decode()),
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

        signers_file = self.mock_signers_file([
            signer1,
            signer2,
        ])

        signers = get_signers(signers_file.name)
        self.assertTrue(set_account_signers(
            horizon_testnet(), pool_kp, signers, SIGNING_THRESHOLD))
