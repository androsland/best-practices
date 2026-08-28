# Infrastructure and deployment

## Managed platform or VPS is a tradeoff, not a rule

S15 promotes a fixed-price VPS, self-managed PostgreSQL, Better Auth, Stripe, and private administration over Tailscale (`S15 00:00–01:28`). The cost concern can be valid, but “you cannot deploy an actual application to Vercel” is opinion, not a technical constraint.

Choose based on workload and organizational capacity.

| Dimension | Managed platform | Self-managed VPS |
|---|---|---|
| Operations | More defaults and automation | You own patching, firewalling, recovery, monitoring, and incidents |
| Pricing | Can scale with usage and managed services | Often predictable base compute cost; labor and failure costs remain |
| Scaling | Platform primitives may reduce work | You design capacity, failover, queues, and scaling |
| Control | Platform constraints | Greater network, runtime, and deployment control |
| Risk | Provider limits and lock-in | Misconfiguration and single-operator risk |

## A decision sequence

1. Model traffic, background work, storage, bandwidth, and growth.
2. Include engineering/on-call time, backups, monitoring, and incident recovery in total cost.
3. Identify constraints: regions, compliance, data locality, cold starts, long-running processes, GPU needs, or custom networking.
4. Compare a realistic managed design with a realistic self-hosted design.
5. Choose the simplest option that meets the current constraints and has a migration path.

## Minimum VPS production baseline

S03 highlights responsibilities hidden by a managed platform (`S03 00:00–02:14`). Before production:

- Use a non-root admin account, key-based SSH, and least privilege.
- Test SSH config and a second access session before disabling password/root access.
- Apply default-deny host and provider firewalls; expose only necessary services.
- Keep the database on a private interface or tightly restricted network path.
- Enable security updates or an immutable-image replacement process, with controlled restart behavior.
- Terminate TLS correctly and automate certificate renewal.
- Centralize logs and monitor availability, disk, memory, database health, authentication failures, and unusual traffic.
- Back up data and configuration; test restoration against RTO/RPO.
- Store secrets outside source control and rotate them.
- Document deployment, rollback, access recovery, and incident response.

Ubuntu documents [OpenSSH configuration](https://ubuntu.com/server/docs/how-to/security/openssh-server/), [UFW](https://ubuntu.com/server/docs/security-firewall/), and the operational caveats of [automatic updates](https://ubuntu.com/server/docs/how-to/software/automatic-updates/).

## Stack notes from S15

- **PostgreSQL:** a strong general-purpose database, but “open source” does not remove operational cost.
- **Better Auth:** presented as an open-source authentication alternative; validate current maturity, security maintenance, adapters, and migration needs before adoption.
- **Stripe:** usage-based payment processing remains an external paid dependency even if application hosting is fixed-price.
- **Tailscale/private administration:** reducing public administrative surface is useful, but the public application still needs defense in depth.

## Source synthesis

- S03: server-hardening responsibilities.
- S15: VPS cost argument and proposed stack.
