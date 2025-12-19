from flask import Blueprint, render_template, request, jsonify, flash
from CTFd.models import db, Submissions, Users, Teams
from CTFd.utils.decorators import admins_only

#Modèles de base de données
class ForbiddenWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class WordAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    word = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'))  
    is_acknowledged = db.Column(db.Boolean, default=False)
    
    # Relations pour pouvoir accéder facilement aux noms
    user = db.relationship('Users', backref='word_alerts')
    team = db.relationship('Teams', backref='word_alerts')
    submission = db.relationship('Submissions', backref='word_alerts')  

class PluginConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_checked_submission_id = db.Column(db.Integer, default=0)
    last_check_count = db.Column(db.Integer, default=0)

def load(app):
    # Drop et recréer les tables à chaque démarrage (pour développement)
    #try:
    #    ForbiddenWord.__table__.drop(app.db.engine, checkfirst=True)
    #    WordAlert.__table__.drop(app.db.engine, checkfirst=True)
    #    PluginConfig.__table__.drop(app.db.engine, checkfirst=True)
    #except Exception as e:
    #    print(f"Info: Tables n'existaient pas encore: {e}")
    
    # Créer les tables de la base de données
    app.db.create_all()
    
    # Initialiser la config SEULEMENT si elle n'existe pas
    config = PluginConfig.query.first()
    if not config:
        latest_submission = Submissions.query.filter(
            Submissions.type != 'pending'
        ).order_by(Submissions.id.desc()).first()
        initial_id = latest_submission.id if latest_submission else 0
        
        config = PluginConfig(last_checked_submission_id=initial_id, last_check_count=0)
        db.session.add(config)
        db.session.commit()

    # Blueprint pour les routes du plugin
    plugin_bp = Blueprint('ctfd_canari_detection', __name__, template_folder='templates')

    # Fonction pour vérifier les nouvelles soumissions depuis le dernier check
    def check_recent_submissions():
        config = PluginConfig.query.first()
        if not config:
            return {'alerts_created': 0, 'new_submissions_count': 0, 'last_submission_id': 0, 'new_alerts': []}
            
        last_checked_id = config.last_checked_submission_id
        
        #print(f"DEBUG: last_checked_id = {last_checked_id}")  # DEBUG
        
        # Récupérer toutes les soumissions depuis le dernier check (en excluant les pending)
        new_submissions = Submissions.query.filter(
            Submissions.id > last_checked_id,
            Submissions.type != 'pending'
        ).order_by(Submissions.id.asc()).all()
        
        #print(f"DEBUG: {len(new_submissions)} nouvelles soumissions trouvées")  # DEBUG
        
        new_submissions_count = len(new_submissions)
        
        if not new_submissions:
            return {'alerts_created': 0, 'new_submissions_count': 0, 'last_submission_id': config.last_checked_submission_id, 'new_alerts': []}
            
        forbidden_words = [word.word.lower() for word in ForbiddenWord.query.all()]
        
        #print(f"DEBUG: Mots surveillés = {forbidden_words}")  # DEBUG
        
        alerts_created = 0
        new_alerts_data = []
        
        for submission in new_submissions:
            submitted_flag = submission.provided.lower() if submission.provided else ''
            
            #print(f"DEBUG: Soumission ID={submission.id}, flag='{submitted_flag}', user_id={submission.user_id}, team_id={submission.team_id}")  # DEBUG
            
            for word in forbidden_words:
                if word in submitted_flag:
                    #print(f"MATCH trouvé ! Mot '{word}' dans '{submitted_flag}'")  # DEBUG
                    
                    # Vérifier si l'alerte n'existe pas déjà pour éviter les doublons
                    existing_alert = WordAlert.query.filter_by(
                        user_id=submission.user_id,
                        team_id=submission.team_id,
                        word=word,
                        submission_id=submission.id 
                    ).first()
                    
                    if not existing_alert:
                        #print(f"Création d'une nouvelle alerte")  # DEBUG
                        alert = WordAlert(
                            user_id=submission.user_id,
                            team_id=submission.team_id,
                            word=word,
                            submission_id=submission.id,
                            is_acknowledged=False
                        )
                        db.session.add(alert)
                        db.session.flush()  # Pour obtenir l'ID
                        
                        # Récupérer les infos utilisateur et équipe pour l'affichage dynamique
                        user = Users.query.get(submission.user_id) if submission.user_id else None
                        team = Teams.query.get(submission.team_id) if submission.team_id else None
                        
                        new_alerts_data.append({
                            'id': alert.id,
                            'user_id': submission.user_id,
                            'user_name': user.name if user else None,
                            'team_id': submission.team_id,
                            'team_name': team.name if team else None,
                            'word': word,
                            'timestamp': alert.timestamp.isoformat() if alert.timestamp else None
                        })
                        
                        alerts_created += 1
                    #else:
                        #print(f"Alerte déjà existante, ignorée")  # DEBUG
        
        # Mettre à jour le dernier ID vérifié et le count
        if new_submissions:
            latest_submission = new_submissions[-1]
            config.last_checked_submission_id = latest_submission.id
        config.last_check_count = new_submissions_count
        db.session.commit()
        
        #print(f"✅ DEBUG: {alerts_created} alertes créées au total")  # DEBUG
        
        return {
            'alerts_created': alerts_created, 
            'new_submissions_count': new_submissions_count,
            'last_submission_id': config.last_checked_submission_id,
            'new_alerts': new_alerts_data
        }

    # Route API pour les actions AJAX
    @plugin_bp.route('/admin/ctfd-canari-detection/api', methods=['POST'])
    @admins_only
    def api_actions():
        action = request.json.get('action')
        word = request.json.get('word')
        words = request.json.get('words')
        alert_id = request.json.get('alert_id')
        
        if action == 'add' and word:
            if not ForbiddenWord.query.filter_by(word=word).first():
                new_word = ForbiddenWord(word=word)
                db.session.add(new_word)
                db.session.commit()
                return jsonify({'success': True, 'message': f'Mot "{word}" ajouté avec succès!'})
            else:
                return jsonify({'success': False, 'message': f'Le mot "{word}" existe déjà!'})
        elif action == 'add_multiple' and words:
            added_count = 0
            existing_count = 0
            added_words = []
            existing_words = []
            
            for word in words:
                if word and not ForbiddenWord.query.filter_by(word=word).first():
                    new_word = ForbiddenWord(word=word)
                    db.session.add(new_word)
                    added_words.append(word)
                    added_count += 1
                elif word:
                    existing_words.append(word)
                    existing_count += 1
            db.session.commit()
            
            message = f'{added_count} mot(s) ajouté(s)'
            if existing_count > 0:
                message += f', {existing_count} mot(s) déjà existant(s)'
                if existing_words:
                    message += f' ({", ".join(existing_words)})'
            
            return jsonify({
                'success': True, 
                'message': message,
                'added_words': added_words,
                'added_count': added_count,
                'existing_count': existing_count,
                'existing_words': existing_words
            })
        elif action == 'delete' and word:
            word_to_delete = ForbiddenWord.query.filter_by(word=word).first()
            if word_to_delete:
                db.session.delete(word_to_delete)
                db.session.commit()
                return jsonify({'success': True, 'message': f'Mot "{word}" supprimé avec succès!'})
        elif action == 'acknowledge' and alert_id:
            alert = WordAlert.query.get(alert_id)
            if alert:
                alert.is_acknowledged = True
                db.session.commit()
                return jsonify({'success': True, 'message': 'Alerte acquittée'})
        elif action == 'check_submissions':
            result = check_recent_submissions()
            return jsonify({
                'success': True, 
                'message': f"{result['alerts_created']} nouvelle(s) alerte(s) créée(s)",
                'alerts_created': result['alerts_created'],
                'new_submissions_count': result['new_submissions_count'],
                'last_submission_id': result['last_submission_id']
            })
        elif action == 'full_analysis':
            # Analyser TOUTES les soumissions du CTF (en excluant les pending)
            forbidden_words = [word.word.lower() for word in ForbiddenWord.query.all()]
            all_submissions = Submissions.query.filter(
                Submissions.type != 'pending'
            ).order_by(Submissions.id.asc()).all()
            
            total_submissions = len(all_submissions)
            alerts_created = 0
            
            for submission in all_submissions:
                submitted_flag = submission.provided.lower() if submission.provided else ''
                
                for word in forbidden_words:
                    if word in submitted_flag:
                        # Vérifier si l'alerte n'existe pas déjà pour éviter les doublons
                        existing_alert = WordAlert.query.filter_by(
                            user_id=submission.user_id,
                            team_id=submission.team_id,
                            word=word,
                            submission_id=submission.id
                        ).first()
                        
                        if not existing_alert:
                            alert = WordAlert(
                                user_id=submission.user_id,
                                team_id=submission.team_id,
                                word=word,
                                submission_id=submission.id,
                                is_acknowledged=False
                            )
                            db.session.add(alert)
                            alerts_created += 1
            
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f"Analyse complète : {alerts_created} alerte(s) créée(s)",
                'alerts_created': alerts_created,
                'total_submissions': total_submissions
            })
        
        return jsonify({'success': False, 'message': 'Action invalide'})

    # Route pour la page d'administration
    @plugin_bp.route('/admin/ctfd-canari-detection', methods=['GET'])
    @admins_only
    def admin_panel():
        # Récupérer les mots interdits et les alertes non acquittées par défaut
        show_acknowledged = request.args.get('show_acknowledged', 'false') == 'true'
        
        forbidden_words = ForbiddenWord.query.all()
        
        # Jointure avec les soumissions en excluant les pending
        if show_acknowledged:
            alerts = WordAlert.query.join(Submissions).filter(
                WordAlert.is_acknowledged==True,
                Submissions.type != 'pending'
            ).order_by(Submissions.date.desc()).all()
        else:
            alerts = WordAlert.query.join(Submissions).filter(
                WordAlert.is_acknowledged==False,
                Submissions.type != 'pending'
            ).order_by(Submissions.date.desc()).all()
            
        # Récupérer l'ID de la dernière soumission analysée
        config = PluginConfig.query.first()
        last_submission_id = config.last_checked_submission_id if config else 0
        last_check_count = config.last_check_count if config else 0
            
        return render_template('alerts.html', 
                             forbidden_words=forbidden_words, 
                             alerts=alerts, 
                             show_acknowledged=show_acknowledged,
                             last_submission_id=last_submission_id,
                             last_check_count=last_check_count)

    # Enregistrer le blueprint
    app.register_blueprint(plugin_bp)