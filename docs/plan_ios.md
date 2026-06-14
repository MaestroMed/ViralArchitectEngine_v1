# FORGE/LAB — Plan global v1.5 → iOS-ready

> Décisions actées (2026-06-14) : **iOS natif Swift**, **upload TikTok via pellicule + Share Sheet**, **accès LAN + clé API simple**.

## Vue d'ensemble

L'audit v1.5 a confirmé que **la moitié "génération auto + review" est déjà solide** :
auto-pipeline qui surveille la chaîne et exporte le top 15 (score ≥ 65), `ClipQueue` avec
flow `pending_review → approved/rejected → scheduled → published`, endpoints `/v1/clips/queue*`
et `/clips/{id}/video` opérationnels. La PWA `web-review` consomme correctement ces routes.

**Ce qui manque pour ton workflow du matin** : durcir le moteur (sécurité + accès), enrichir
quelques endpoints mobiles, et construire l'app iOS native.

Le plan tient en **3 phases** dans cet ordre (chaque phase est indépendamment déployable).

---

## Phase 1 — Durcissement backend + enrichissement API mobile (~1 semaine)

> Objectif : un moteur sûr, atteignable depuis le tel sur le LAN, avec les routes qu'il faut pour l'app iOS.

### 1.1 Accès distant + auth (blocker #1)
- `core/config.py:18` — passer `HOST` de `127.0.0.1` à `0.0.0.0` quand `FORGE_BIND_LAN=1` (nouveau, default off pour rester local).
- Nouveau middleware `core/auth.py` : auth par clé API (header `X-API-Key`), dépendance FastAPI à appliquer sur **toutes** les routes `/v1/*` sauf `/health`. Clés stockées dans une table `api_keys` (label + hash + last_used_at), seedable via une commande CLI.
- `core/config.py` — ajouter `CORS_ORIGIN_REGEX` (autoriser `http://192.168.*.*:*` quand bind LAN).
- README + `.env.example` : section "Accès depuis le téléphone" (bind LAN, créer une clé API, configurer l'IP dans l'app iOS).

### 1.2 Sécurité — P0 sociaux + LLM
- `services/social_publish.py:87,124` — sortir les credentials de la RAM : nouveau modèle `SocialAccount` chiffré (SQLAlchemy `TypeDecorator` + clé symétrique dérivée de `FORGE_SECRET_KEY`).
- `services/analytics.py:221,256,290` — couper les logs httpx au-dessus de WARNING, scrubber Authorization headers.
- `services/llm_local.py:174,325` — passer le transcript via `json.dumps()` (échappement) + valider la structure de la réponse LLM (Pydantic).
- Nouveau middleware rate-limit (slowapi ou maison) sur `/v1/{llm,translation,content,ml_scoring,social}/*` : 10 req/min/IP par défaut, configurable.

### 1.3 Endpoints `social.py` cassés
- `api/v1/endpoints/social.py:45,55,74,93,97,116,144` appelle 4 méthodes inexistantes (`get_connected_platforms`, `connect_account`, `disconnect_account`, `get_publish_status`). Trois options : (a) les implémenter dans `SocialPublishService` proprement, (b) supprimer les routes, (c) renvoyer `501 Not Implemented` explicite. → Recommandation : (a), c'est de toute façon la prochaine étape avec les credentials persistés.

### 1.4 Enrichissement API mobile
- `GET /v1/clips/by-date?date=YYYY-MM-DD&channel=…` — filtre la `ClipQueue` par `created_at` (la requête "clips d'hier" en 1 call au lieu de tout récupérer).
- `GET /v1/clips/{id}/bundle.zip` — ZIP signé contenant `clip.mp4` + `cover.jpg` + `metadata.json` (titre, hashtags, légende). Endpoint streamé (zipfile en mémoire OK pour des clips de quelques MB).
- `POST /v1/clips/batch-approve` — payload `{ids: [...]}`, transaction unique, retourne le décompte.
- `GET /v1/clips/{id}/cover` — sert la miniature seule (l'app iOS l'utilise pour la liste).
- **Fix subtil mais important** : `/clips/{id}/video` (`main.py:246`) annonce `Accept-Ranges: bytes` mais `FileResponse` ne sert pas réellement les Range requests (HTTP 206). À remplacer par un handler Range proprement implémenté (sinon le preview iOS DL tout le clip à chaque tap). Référence : *Starlette `FileResponse` + manual range parsing* ou util `fastapi-range`.

### 1.5 Hygiène repo (pré-requis CI propre)
- `apps/desktop/electron/{main.js,preload.js,*.d.ts}` + `tsconfig.node.tsbuildinfo` — désuivre (`git rm --cached`), ajouter au `.gitignore`. Vérifier d'abord qu'`electron-builder.config.js` ne pointe pas sur ces fichiers (sinon ajuster le build pour qu'il les produise à la volée).
- `apps/desktop/package-lock.json` — supprimer (workspace pnpm).
- `apps/desktop/scripts/prepare-python.js` — ajouter vérification SHA256 sur les téléchargements Python embed + FFmpeg (constantes en haut du fichier, fail-fast si mismatch).
- `electron/main.ts:72,78,122,139,143,156,164,170` — guarder les `console.log` derrière `if (process.env.NODE_ENV !== 'production')`.

### 1.6 Job system (dette technique — à faire avant l'app iOS, pas urgent)
- `core/jobs.py:230,271,335` — ajouter colonne `payload` (migration légère `ALTER TABLE` au startup, comme fait précédemment), arrêter d'écrire les kwargs dans `result`. Les lectures lisent les deux pendant la transition.
- Introduire Alembic pour les futures migrations (les nouveaux modèles `review.py` + `training_data.py` ont été créés via `create_all` — fragile dès qu'on touche un schéma).

### Verif Phase 1
- `pnpm lint && pnpm typecheck && pnpm test` ; `ruff check src/` ; `pytest tests/`
- Tel sur le même WiFi → `curl http://<ip-pc>:8420/v1/clips/queue/pending -H "X-API-Key: <clé>"` retourne du JSON.
- `curl http://<ip-pc>:8420/v1/clips/<id>/bundle.zip` → ZIP valide.
- `curl http://<ip-pc>:8420/clips/<id>/video -H "Range: bytes=0-1023"` → HTTP **206** avec 1024 octets.

---

## Phase 2 — App iOS native (~2-3 semaines)

> **SwiftUI**, iOS 17+. Distribution TestFlight (compte Apple Developer requis, 99 $/an). Pas de Mac → blocant.

### 2.1 Architecture
- **SwiftPM only**, pas de CocoaPods. Dépendances : `KeychainAccess` (clé API), aucune autre.
- **Pas de SwiftData/CoreData** au début : tout vient de l'API, cache en mémoire + `URLCache` pour les images.
- **3 écrans** :
  1. **Onboarding/Settings** : IP du moteur, clé API, test de connexion. Stockage dans Keychain.
  2. **Queue** : feed vertical des clips `pending_review` (date par défaut = hier), tri par score. Tap → détail.
  3. **Clip detail** : `AVPlayer` (preview via Range requests sur `/clips/{id}/video`), score, transcript, hashtags. Boutons : **Approve**, **Reject**, **Download to Photos**, **Copy caption + Open TikTok**.

### 2.2 Network layer
- `URLSession` + `async/await`. Une classe `ForgeAPI` qui prend `(baseURL, apiKey)`, expose les méthodes typées.
- Codables miroitant les schémas backend (à garder synchronisés — voir aussi P2.7 du précédent audit : on peut générer ces types depuis `packages/shared/zod` plus tard).

### 2.3 Workflow "Download to Photos + TikTok"
- DL du `bundle.zip` (clip + cover + metadata) dans tmp.
- Sauvegarde du `.mp4` dans la pellicule via `PHPhotoLibrary.shared().performChanges`.
- Copie de la légende (titre + hashtags) dans `UIPasteboard.general`.
- Ouverture de TikTok (`URL(string: "tiktok://")`) ou Share Sheet (`UIActivityViewController`) pré-rempli avec le clip.
- Marquage automatique `status = published` côté backend après confirmation user (bouton "Posté ✓").

### 2.4 Notifs (optionnel mais utile)
- Backend : webhook configurable `FORGE_NOTIFY_URL`, déclenché par `auto_pipeline.py` quand de nouveaux clips entrent dans la queue.
- App iOS : pas d'APNS au début (lourd à setup). À la place, **badge sur l'icône** via une notif locale déclenchée quand l'app s'ouvre et trouve des `pending_review` plus récents que la dernière session.

### 2.5 Tests
- Snapshot tests SwiftUI sur les 3 écrans.
- Tests d'intégration `ForgeAPI` avec `URLProtocolMock`.

### Verif Phase 2
- TestFlight installé sur l'iPhone, l'app se connecte, le feed liste les clips d'hier, preview vidéo fluide (grâce au Range correct), download + TikTok en moins de 5 secondes.

---

## Phase 3 — Affiner l'automatisation matinale (~1 semaine)

> Pour que les clips soient **vraiment prêts** à 7h du matin.

### 3.1 Trigger sur fin de VOD (au lieu du poll 30 min)
- `services/auto_pipeline.py:31` (`check_interval=1800`) reste comme filet, mais ajouter un endpoint **webhook Twitch** (`stream.offline` event sub) qui déclenche le pipeline immédiatement à la fin du stream.
- Variable d'env `FORGE_TWITCH_WEBHOOK_SECRET` pour valider les signatures HMAC.

### 3.2 Fenêtre d'export configurable
- `auto_pipeline.py:248` exporte immédiatement après analyse → option `FORGE_EXPORT_WINDOW=05:00-07:00` qui diffère l'export à cette fenêtre (load GPU la nuit, queue propre au réveil).

### 3.3 Timezone propre
- `publish_scheduler.py:17-22` codé en dur sur Paris → lire `FORGE_TIMEZONE` (Europe/Paris par défaut), passer par `zoneinfo`.

### 3.4 Notifications
- Email/Slack/webhook quand la queue du matin est prête, avec compte de clips et lien deep-link `forgelab://queue?date=…` ouvrant l'app iOS sur la bonne date.

---

## Hors-périmètre pour l'instant (notés)

- **Refactor sécurité avancée** : `social_publish.py` méthodes manquantes + persistance chiffrée des creds — fait en Phase 1.2/1.3.
- **`apps/web-review` PWA** : on la garde fonctionnelle (review depuis ordi/tablette) mais elle n'est pas la cible iOS. Elle profite des durcissements API gratuitement.
- **TikTok API officielle** : si un jour ton compte est approuvé, on bascule de "pellicule + share sheet" à publish 1-tap, mais c'est un add-on, pas un blocker.
- **Tests E2E pipeline réel** : `test_pipeline_e2e.py` ne mocke pas tout, à étoffer en parallèle des phases ci-dessus.

---

## Ordre d'exécution recommandé

1. **Phase 1.1 + 1.5** d'abord (auth + bind LAN + hygiène repo) → débloque tout le reste, faible risque.
2. **Phase 1.4 + 1.6** (API mobile + payload column) → permet à l'app iOS d'avoir un contrat stable et propre.
3. **Phase 1.2 + 1.3** (sécurité sociale) → peut se faire en parallèle de la phase 2 dès qu'elle commence.
4. **Phase 2** (app iOS) — quand Phase 1 est merge.
5. **Phase 3** — quand Phase 2 est en TestFlight.

## Pré-requis humains à valider

- Compte Apple Developer activé (99 $/an) avant de démarrer Phase 2.
- Accès au PC fixe (où tourne le moteur) avec IP LAN stable (réservation DHCP) pour le tel.
- Si tu veux Phase 3.1 : créer une app Twitch dev pour les webhooks EventSub.
