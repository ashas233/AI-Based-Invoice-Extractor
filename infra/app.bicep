targetScope = 'resourceGroup'

param location string
param appName string
param environmentName string
param acrLoginServer string
param identityName string
param storageAccountName string
param imageTag string

@secure()
param anthropicApiKey string

param enableEntraAuth bool
param publicIngress bool
param entraClientId string
param entraTenantId string
param entraAllowedUserObjectId string

@secure()
param entraClientSecret string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource environmentStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: environment
  name: 'invoice-data'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys('2023-01-01').keys[0].value
      shareName: 'invoice-data'
      accessMode: 'ReadWrite'
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${pullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: pullIdentity.id
        }
      ]
      secrets: concat(
        [
          {
            name: 'anthropic-api-key'
            value: anthropicApiKey
          }
        ],
        enableEntraAuth
          ? [
              {
                name: 'entra-client-secret'
                value: entraClientSecret
              }
            ]
          : []
      )
      ingress: {
        external: publicIngress
        allowInsecure: false
        targetPort: 8501
        transport: 'auto'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/invoice-extractor:${imageTag}'
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            {
              name: 'ANTHROPIC_API_KEY'
              secretRef: 'anthropic-api-key'
            }
            {
              name: 'DB_BACKEND'
              value: 'sqlite'
            }
            {
              name: 'DB_PATH'
              value: '/srv/data/invoices.db'
            }
            {
              name: 'HF_HOME'
              value: '/srv/data/huggingface'
            }
          ]
          volumeMounts: [
            {
              volumeName: 'invoice-data'
              mountPath: '/srv/data'
            }
          ]
        }
        {
          name: 'ui'
          image: '${acrLoginServer}/invoice-extractor:${imageTag}'
          command: [
            'streamlit'
          ]
          args: [
            'run'
            'ui/streamlit_app.py'
            '--server.address'
            '0.0.0.0'
            '--server.port'
            '8501'
          ]
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
          env: [
            {
              name: 'API_URL'
              value: 'http://127.0.0.1:8000'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: [
        {
          name: 'invoice-data'
          storageType: 'AzureFile'
          storageName: environmentStorage.name
        }
      ]
    }
  }
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (enableEntraAuth) {
  parent: app
  name: 'current'
  properties: {
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureActiveDirectory'
    }
    httpSettings: {
      requireHttps: true
      forwardProxy: {
        convention: 'Standard'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-client-secret'
          openIdIssuer: 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              identities: [
                entraAllowedUserObjectId
              ]
            }
          }
        }
      }
    }
  }
}

output siteUrl string = 'https://${appName}.${environment.properties.defaultDomain}'
