# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Global Credit Core system.

## Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- NGINX Ingress Controller (for Ingress)
- Metrics Server (for HPA)
- Prometheus Operator (optional, for ServiceMonitor)

## Quick Deploy

```bash
# Apply all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods
kubectl get services
kubectl get hpa
```

## Individual Components

```bash
# Secrets (IMPORTANT: Update with real values before deploying)
kubectl apply -f k8s/secret.yaml

# ConfigMap
kubectl apply -f k8s/configmap.yaml

# Resource Quotas and Limits
kubectl apply -f k8s/resourcequota.yaml

# Services
kubectl apply -f k8s/service.yaml

# Deployments
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-worker.yaml
kubectl apply -f k8s/deployment-frontend.yaml

# Network Policies (for network isolation)
kubectl apply -f k8s/networkpolicy.yaml

# Pod Disruption Budgets (for availability during updates)
kubectl apply -f k8s/poddisruptionbudget.yaml

# Horizontal Pod Autoscalers
kubectl apply -f k8s/hpa.yaml

# ServiceMonitor (requires Prometheus Operator)
kubectl apply -f k8s/servicemonitor.yaml

# Ingress
kubectl apply -f k8s/ingress.yaml
```

## Scaling

The system includes Horizontal Pod Autoscalers (HPA) that automatically scale:

- **API**: 3-10 replicas based on CPU/memory usage
- **Workers**: 2-20 replicas based on CPU usage

Manual scaling:
```bash
kubectl scale deployment credit-api --replicas=5
kubectl scale deployment credit-worker --replicas=10
```

## Monitoring

```bash
# Watch pods
kubectl get pods -w

# Check HPA status
kubectl get hpa

# View logs
kubectl logs -f deployment/credit-api
kubectl logs -f deployment/credit-worker
```

## Architecture Notes

- **API**: 3 replicas minimum for high availability
- **Workers**: 5 replicas for concurrent processing
- **Frontend**: 2 replicas
- **Load Balancing**: Handled by Kubernetes Services
- **Auto-scaling**: HPA based on CPU and memory metrics
- **WebSocket**: Supported via Ingress annotations

## Security Features

- **Network Policies**: Isolated network traffic between components
  - API pods can only communicate with database and Redis
  - Frontend pods can only communicate with API
  - Workers can only communicate with database and Redis
  - Database and Redis only accept connections from authorized pods

- **Secrets**: Sensitive data stored in Kubernetes Secrets
  - Database credentials
  - JWT secrets
  - Webhook secrets
  - Encryption keys

- **Resource Quotas**: Limits on namespace resource consumption
  - Prevents resource exhaustion
  - Enforces default resource requests/limits

- **Pod Disruption Budgets**: Ensures minimum availability during updates
  - API: Minimum 2 pods available
  - Frontend: Minimum 1 pod available
  - Workers: Minimum 2 pods available

## Production Considerations

1. **Secrets Management**: 
   - Update `secret.yaml` with real base64-encoded values
   - Use external secret management (Vault, AWS Secrets Manager, Azure Key Vault)
   - Rotate secrets regularly

2. **Database**: Deploy PostgreSQL as StatefulSet with persistence

3. **Redis**: Deploy Redis as StatefulSet or use managed service

4. **Monitoring**: 
   - ServiceMonitor configured for Prometheus Operator
   - Add Prometheus/Grafana for observability
   - Configure alerting rules

5. **Backup**: Implement database backup strategy

6. **TLS**: Enable TLS termination in Ingress

7. **Network Policies**: Review and adjust network policies based on your security requirements

8. **Resource Quotas**: Adjust resource quotas based on cluster capacity and requirements
