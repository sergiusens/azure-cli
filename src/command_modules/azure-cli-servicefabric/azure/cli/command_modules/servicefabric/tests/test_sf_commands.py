# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import unittest
from azure.cli.testsdk import ScenarioTest, ResourceGroupPreparer


class ServiceFabricTests(ScenarioTest):

    def test_create(self):

        self.kwargs.update({
            'name': 'sfcli7',
            'rg': 'sfcli7',
            'location': 'westus'
        })

        self.cmd('sf cluster create --resource-group {rg} --location {location} --cluster-size 1 --secret-identifier '
                 'https://sfcli4.vault.azure.net/secrets/sfcli4201708250843/2b9981be18164360a21e6face7b67a77 '
                 '--vm-password User@123456789',
                 checks=[self.check('cluster.name', '{name}')])

    def test_client_cert(self):
        test_thumbprint = '9B609A389BD4597BEEFABFB363BF2BBF2E806001'

        self.kwargs.update({
            'name': 'sfcli1',
            'rg': 'sfcli1',
            'test_thumbprint': test_thumbprint
        })

        self.cmd('sf cluster list --resource-group {rg}',
                 checks=[self.check('type(@)', 'array')])

        self.cmd('sf cluster show --resource-group {rg} --name {name}',
                 checks=[self.check('name', '{name}')])

        self.cmd('sf cluster upgrade-type set --resource-group {rg} --cluster-name {name} --upgrade-mode automatic',
                 checks=[self.check('upgradeMode', 'Automatic')])

        self.cmd('sf cluster client-certificate add --resource-group {rg} --name {name}  --thumbprint {test_thumbprint}',
                 checks=[self.check('clientCertificateThumbprints[0].certificateThumbprint', '{test_thumbprint}'),
                         self.check('clientCertificateThumbprints[0].isAdmin', False)])

        self.cmd('sf cluster client-certificate remove --resource-group {rg} --name {name} --thumbprints {test_thumbprint}',
                 checks=[self.check('length(clientCertificateThumbprints)', 0)])

    def test_remove_node(self):
        self.kwargs.update({
            'name': 'sfcli6',
            'rg': 'sfcli6'
        })
        self.cmd('sf cluster node remove -g {rg} -n {name} --node-type nt1vm  --number-of-nodes-to-remove 1',
                 checks=[self.check('nodeTypes[0].vmInstanceCount', 5)])

    def test_reliability(self):
        self.kwargs.update({
            'name': 'sfcli6',
            'rg': 'sfcli6',
            'reliability_level': 'Silver'
        })
        self.cmd('sf cluster reliability update --resource-group {rg} --name {name} --reliability-level {reliability_level}',
                 checks=[self.check('reliabilityLevel', '{reliability_level}')])

    def test_durability(self):
        name = 'appcanary'
        durability_level = 'Bronze'

        self.kwargs.update({
            'name': name,
            'rg': 'appcanary-rg',
            'durability_level': durability_level
        })

        self.cmd('sf cluster durability update --resource-group {rg} --name {name} --durability-level {durability_level} --node-type FE',
                 checks=[self.check('nodeTypes[0].durabilityLevel', '{durability_level}')])

    def test_node(self):
        name = 'sfcli7'

        self.kwargs.update({
            'name': name,
            'rg': 'sfcli7'
        })

        self.cmd('sf cluster node add -g {rg} -n {name} --node-type nt1vm  --number-of-nodes-to-add 1',
                 checks=[self.check('nodeTypes[0].vmInstanceCount', 2)])

    def test_setting(self):
        name = 'sfcli2'

        self.kwargs.update({
            'name': name,
            'rg': 'sfcli2'
        })

        self.cmd('sf cluster setting set --resource-group {rg} --name {name} --section NamingService --parameter MaxOperationTimeout --value 10001',
                 checks=[self.check('fabricSettings[1].name', 'NamingService'),
                         self.check(
                             'fabricSettings[1].parameters[0].name', 'MaxOperationTimeout'),
                         self.check('fabricSettings[1].parameters[0].value', '10001')])

        self.cmd('sf cluster setting remove --resource-group {rg} --name {name} --section NamingService --parameter MaxOperationTimeout',
                 checks=[self.check('length(fabricSettings)', 1)])

    def test_cluster_cert(self):
        name = 'sfcli4'

        self.kwargs.update({
            'name': name,
            'rg': 'sfcli4'
        })

        cluster = self.cmd(
            'sf cluster certificate add --resource-group {rg} --cluster-name {name} --secret-identifier https://sfcli4.vault.azure.net/secrets/sfcli4201708250843/2b9981be18164360a21e6face7b67a77')
        assert cluster['certificate']['thumbprintSecondary']

        self.kwargs.update({
            'thumb2': cluster['certificate']['thumbprintSecondary']
        })

        cluster = self.cmd('sf cluster certificate remove --resource-group {rg} --cluster-name {name} --thumbprint {thumb2}')
        assert not cluster['certificate']['thumbprintSecondary']


if __name__ == '__main__':
    unittest.main()
