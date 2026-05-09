# TP Programmation Parallèle

## ✍️ Auteurs

- 👤 **Morisho Nyembo Delphin**
- 👤 **Danniel Muledi**

## 📋 Description du logiciel

Ce projet est un système de chat client-serveur sécurisé développé en Python. Il permet aux utilisateurs d'échanger des messages de manière chiffrée via une interface graphique. Le système supporte trois modes de communication :
- **Messages privés** : Communication directe entre deux utilisateurs
- **Messages de groupe** : Communication avec plusieurs destinataires sélectionnés
- **Messages broadcast** : Diffusion à tous les utilisateurs connectés

Le serveur gère les connexions clients, stocke les messages dans une base de données MySQL et assure la sécurité grâce au chiffrement Fernet. L'interface utilisateur est réalisée avec Tkinter pour une expérience conviviale.

## 🔧 Requirements

- **Python** : Version 3.7 ou supérieure
- **MySQL** : Serveur MySQL (version 8.0 recommandée)
- **Bibliothèques Python** :
  - mysql-connector-python==8.0.33
  - cryptography==41.0.7

## 🚀 Procédure d'installation

1. **Cloner le repository** :
   ```bash
   git clone <url-du-repository>
   cd TP_Programationparallel
   ```

2. **Installer Python** :
   Assurez-vous que Python 3.7+ est installé sur votre système. Vous pouvez vérifier avec :
   ```bash
   python3 --version
   ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer MySQL** :
   - Installez et démarrez MySQL
   - Créez une base de données nommée `chat_db`
   - Importez le schéma de base de données :
     ```bash
     mysql -u root -p chat_db < chat_db.sql
     ```

5. **Configurer les variables d'environnement** (optionnel) :
   - Définissez `CHAT_SECRET` pour la clé de chiffrement :
     ```bash
     export CHAT_SECRET="votre-cle-secrete-personnalisee"
     ```

6. **Lancer le serveur** :
   ```bash
   python3 serveur.py
   ```

7. **Lancer les clients** :
   Ouvrez plusieurs terminaux et exécutez :
   ```bash
   python3 client.py
   ```

Le serveur doit être démarré en premier, puis les clients peuvent se connecter.

