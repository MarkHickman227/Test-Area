# ApplyPilot AWS deployment (optional)

**Not the primary target.** Production is the **Hostinger VPS** — see `docs/vps-deployment.md`.

Keep this doc only if you later move ApplyPilot to AWS (ECS Fargate + Secrets Manager + CloudWatch).

## Sketch

| Piece | AWS service |
|-------|-------------|
| App | ECS Fargate + ALB |
| Images | ECR |
| Secrets | Secrets Manager |
| Schedule | In-app twice-daily + optional EventBridge backup |
| Monitor | CloudWatch |

Rough infra cost: ~\$35–50/mo with ALB — higher than the VPS path (~£5–13/mo).

Do not use this path unless explicitly chosen over the VPS.
