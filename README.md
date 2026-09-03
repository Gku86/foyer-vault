# Dépôt Home Assistant — HomeBudget + Foyer Vault

Deux applications, **indépendantes** :

| Dossier | Rôle | Port |
|---|---|---|
| `foyer-vault/` | Coffre chiffré (à garder) | 8099 |
| `homebudget/` | Interface HomeBudget | 8100 |

## GitHub

Racine du dépôt :

```text
repository.yaml
foyer-vault/
homebudget/
```

Dans HA : **Paramètres → Applications → ⋮ → Dépôts** →
`https://github.com/Gku86/foyer-vault`

## Cloudflare

Ne pas mélanger les hostnames :

| Hostname | Service |
|---|---|
| `foyer.fchvtn.ovh` | `http://127.0.0.1:8099` (vault, déjà en place) |
| un autre, ex. `budget.fchvtn.ovh` | `http://127.0.0.1:8100` (interface) |

## Mises à jour

Incrémenter `version` dans `homebudget/config.yaml`, pousser, puis HA → **Mettre à jour**.
Foyer Vault n’est pas touché, **sauf** la 1.3.0 (fichiers chiffrés), la **1.3.1** (notifications iPhone), la **1.3.2** (notifications d’un appareil vers un autre), la **1.3.3** (identifiant unique par appareil) et la **1.3.4** (nom d’utilisateur + anciens identifiants fusionnés). Dans ces cas, mettre à jour les deux modules.

