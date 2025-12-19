# CTFD-Canari-Detection

**CTFD-Canari-Detection** est un plugin pour [CTFd](https://ctfd.io) permettant aux administrateurs de détecter automatiquement les soumissions contenant des mots suspects ou des flags "canaris" (honeypots).

---

## Fonctionnalités principales

- **Détection automatique de canaris** :
  - Surveillez les soumissions pour détecter des flags ou mots spécifiques (canaris/honeypots).
  - Idéal pour identifier les tricheurs, fuites de flags, ou comportements suspects.
  - Chaque soumission contenant un canari génère une alerte unique.

- **Gestion des mots surveillés** :
  - Ajoutez, modifiez ou supprimez facilement les mots à surveiller depuis l'interface admin.
  - Ajout multiple de mots en une seule fois (séparés par des points-virgules).
  - Recherche et filtrage des mots surveillés.

- **Système d'alertes intelligent** :
  - Toutes les détections génèrent des alertes avec informations complètes (utilisateur, équipe, mot détecté, challenge, timestamp).
  - Chaque soumission crée une alerte distincte, permettant de tracker les tentatives multiples.
  - Acquittement des alertes pour marquer celles qui ont été traitées.
  - Filtrage entre alertes actives et acquittées.
  - Recherche d'alertes par utilisateur, équipe ou mot détecté.

- **Analyses flexibles** :
  - **Détection incrémentale** : Analysez uniquement les nouvelles soumissions depuis la dernière vérification.
  - **Analyse complète** : Scannez l'intégralité de l'historique des soumissions du CTF.
  - Feedback en temps réel avec durée d'exécution et nombre d'alertes créées.

- **Interface intuitive** :
  - Dashboard avec statistiques en temps réel (alertes actives, mots surveillés, dernière analyse).
  - Design moderne avec feedback visuel des opérations.
  - Ajout dynamique des mots sans rechargement de page.

- **Support mode équipe et individuel** :
  - Fonctionne aussi bien en mode TEAM qu'en mode USER de CTFd.
  - Détection adaptée selon le mode de jeu configuré.

## Pourquoi ce plugin ?

> "Comment détecter si quelqu'un soumet des flags qui ne devraient pas être connus ?"

Avec ce plugin, les organisateurs peuvent placer des "canaris" (faux flags ou mots-clés) pour détecter :
- **Tricheurs** qui copient des flags d'autres équipes
- **Fuites** de flags (writeups publiés trop tôt, partage entre équipes)
- **Comportements suspects** (brute force, scraping, tentatives multiples)
- **Patterns d'attaque** en analysant la fréquence des soumissions

Les administrateurs gagnent en visibilité sur les activités suspectes et peuvent réagir rapidement sans avoir à analyser manuellement des milliers de soumissions.

Grâce à ce plugin, vous maintenez l'intégrité de votre compétition et garantissez une expérience équitable pour tous les participants.

## Installation

1. Clonez ce dépôt dans le dossier `CTFd/plugins` :
```bash
   cd /path/to/CTFd/plugins
   git clone https://github.com/HACK-OLYTE/CTFD-Canari-Detection.git
```

2. Redémarrez votre instance CTFd pour charger le plugin.

3. Les tables de base de données seront créées automatiquement au premier démarrage.

## Configuration

Accédez au panneau d'administration **Plugins > Canari Détection** pour :

- **Ajouter des mots à surveiller** : 
  - Entrez un ou plusieurs mots/flags séparés par des points-virgules (;)
  - Exemple : `flag{fake123};canari_secret;test_flag`
  - Les mots sont détectés de manière insensible à la casse (case-insensitive)

- **Lancer des détections** :
  - **Détection incrémentale** : Analysez uniquement les nouvelles soumissions depuis la dernière analyse
  - **Analyse complète** : Scannez tout l'historique (attention : peut être long sur gros CTF)

- **Gérer les alertes** :
  - Consultez les alertes actives avec détails complets
  - Acquittez les alertes traitées pour les archiver
  - Recherchez par utilisateur, équipe ou mot détecté
  - Basculez entre alertes actives et acquittées

Voici une vidéo de démonstration :

https://github.com/user-attachments/assets/7525a7a9-530c-41c4-9fae-1a3cd246bf25

## Fonctionnement technique

Le plugin :
1. Stocke une liste de mots "canaris" en base de données
2. Analyse les soumissions (nouvelles ou toutes selon le mode)
3. Détecte si une soumission contient un mot surveillé (recherche insensible à la casse, substring)
4. Génère automatiquement une alerte avec toutes les informations contextuelles
5. **Crée une alerte par soumission** : Si un utilisateur soumet le même canari plusieurs fois (même sur le même challenge), chaque soumission génère une alerte distincte
6. Évite les vrais doublons (même soumission analysée plusieurs fois)

**Note** : Les soumissions de type "pending" sont automatiquement exclues de l'analyse.

## Comportement des alertes

### Gestion des doublons intelligente :

- **Même mot, même challenge, même soumission** → Pas de doublon ✅
- **Même mot, même challenge, soumissions différentes** → Nouvelles alertes créées ✅
- **Même mot, challenges différents** → Nouvelles alertes créées ✅

**Exemple concret :**
1. L'utilisateur MBAY soumet `elephant` sur le challenge "Web 1" → Alerte créée
2. Admin acquitte l'alerte
3. MBAY soumet **à nouveau** `elephant` sur "Web 1" → **Nouvelle alerte créée** (permet de détecter les tentatives répétées)
4. MBAY soumet `elephant` sur "Crypto 5" → **Nouvelle alerte créée** (challenge différent)

Ce comportement permet de :
- Tracker le nombre de tentatives avec un canari
- Détecter le brute force ou comportements suspects
- Avoir une vision complète de l'utilisation des canaris

## Cas d'usage

### 1. Détection de triche
Créez des faux flags et placez-les dans des endroits accessibles uniquement par triche (ex: base de données factice, fichiers non liés aux challenges). Si quelqu'un les soumet → alerte !

### 2. Détection de fuites
Après un incident où un flag a fuité, ajoutez-le comme canari. Vous saurez instantanément qui l'a utilisé et combien de fois.

### 3. Honeypot challenges
Créez des challenges "pièges" avec des flags canaris pour identifier les équipes qui partagent des solutions.

### 4. Analyse comportementale
Surveillez les tentatives répétées avec le même canari pour détecter du brute force ou des scripts automatisés.

## Dépendances

- CTFd ≥ v3.8.1
- Compatible avec les installations Docker et locales
- Un navigateur à jour avec JavaScript activé
- CTFd thème : Core-beta (testé et optimisé)

## Sécurité

Ce plugin a été conçu avec la sécurité en priorité :
- ✅ Protection XSS avec échappement automatique (Jinja2 `| e` et DOM manipulation)
- ✅ Routes admin protégées avec `@admins_only`
- ✅ Pas d'injection SQL (utilisation ORM SQLAlchemy)
- ✅ Protection CSRF native de CTFd
- ✅ Validation des données côté serveur
- ✅ Pas de doublons d'alertes grâce à la vérification en base par `submission_id`
- ✅ Debouncing et rate limiting côté client pour éviter le spam serveur

## Limitations

- La détection est basée sur une recherche simple de substring (case-insensitive)
- L'analyse complète peut être lente sur de très gros CTF (100k+ submissions)
- Les canaris doivent être ajoutés manuellement par les administrateurs
- Chaque soumission d'un canari génère une alerte (peut créer beaucoup d'alertes si spam)

## Support

Pour toute question ou problème, ouvrez une [issue](https://github.com/HACK-OLYTE/CTFD-Canari-Detection/issues).  
Ou contactez-nous sur le site de l'association Hack'olyte : [contact](https://hackolyte.fr/contact/).

## Contribuer

Les contributions sont les bienvenues !  
Vous pouvez :
- Signaler des bugs
- Proposer de nouvelles fonctionnalités (ex: webhooks Discord, regex patterns, alertes par email, etc.)
- Soumettre des pull requests
- Améliorer la documentation

## Crédits

Développé avec ❤️ par l'association [Hack'olyte](https://hackolyte.fr)

## Licence

Ce plugin est sous licence [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.fr).  
Merci de ne pas retirer le footer de chaque fichier HTML sans l'autorisation préalable de l'association Hack'olyte.

---

**Note** : Ce plugin ne modifie pas les challenges ou les soumissions, il fonctionne uniquement en lecture et génère des alertes pour les administrateurs. Les données sont stockées dans des tables dédiées qui n'interfèrent pas avec le fonctionnement normal de CTFd.
