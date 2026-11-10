targetScope = 'resourceGroup'

@description('Lowercase letters and digits only; use a short unique prefix.')
@minLength(3)
@maxLength(8)
param namePrefix string

param location string = resourceGroup().location

@description('Object ID of the GitHub Actions deployment service principal.')
param deploymentPrincipalObjectId string

var suffix = uniqueString(resourceGroup().id)
var acrName = take('${namePrefix}${suffix}', 50)
var storageAccountName = take('st${namePrefix}${suffix}', 24)
var environmentName = take('cae-${namePrefix}-${suffix}', 24)
var identityName = take('id-${namePrefix}-${suffix}', 24)
var appName = take('invoice-${namePrefix}-${suffix}', 32)
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)
var acrPushRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource invoiceShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: 'invoice-data'
  properties: {
    shareQuota: 5
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'none'
    }
  }
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource identityAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, pullIdentity.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource githubAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, deploymentPrincipalObjectId, acrPushRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPushRoleId
    principalId: deploymentPrincipalObjectId
    principalType: 'ServicePrincipal'
  }
}

output acrName string = registry.name
output acrLoginServer string = registry.properties.loginServer
output storageAccountName string = storage.name
output environmentName string = environment.name
output identityName string = pullIdentity.name
output appName string = appName
