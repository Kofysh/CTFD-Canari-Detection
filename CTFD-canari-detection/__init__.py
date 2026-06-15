from flask import Blueprint, render_template, request, jsonify
from CTFd.models import db, Submissions, Users, Teams
from CTFd.utils.decorators import admins_only
from sqlalchemy.orm import joinedload

BATCH_SIZE = 1000


class ForbiddenWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class WordAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True, index=True)
    word = db.Column(db.String(255), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), index=True)
    is_acknowledged = db.Column(db.Boolean, default=False, index=True)

    user = db.relationship('Users', backref='word_alerts')
    team = db.relationship('Teams', backref='word_alerts')
    submission = db.relationship('Submissions', backref='word_alerts')


class PluginConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_checked_submission_id = db.Column(db.Integer, default=0)
    last_check_count = db.Column(db.Integer, default=0)


def load(app):
    app.db.create_all()

    config = PluginConfig.query.first()
    if not config:
        latest = Submissions.query.filter(
            Submissions.type != 'pending'
        ).order_by(Submissions.id.desc()).first()
        config = PluginConfig(
            last_checked_submission_id=latest.id if latest else 0,
            last_check_count=0
        )
        db.session.add(config)
        db.session.commit()

    plugin_bp = Blueprint('ctfd_canari_detection', __name__, template_folder='templates')

    def check_recent_submissions():
        config = PluginConfig.query.first()
        if not config:
            return {'alerts_created': 0, 'new_submissions_count': 0, 'last_submission_id': 0, 'new_alerts': []}

        new_submissions = Submissions.query.filter(
            Submissions.id > config.last_checked_submission_id,
            Submissions.type != 'pending'
        ).order_by(Submissions.id.asc()).all()

        new_submissions_count = len(new_submissions)

        if not new_submissions:
            return {
                'alerts_created': 0,
                'new_submissions_count': 0,
                'last_submission_id': config.last_checked_submission_id,
                'new_alerts': []
            }

        forbidden_words = [w.word.lower() for w in ForbiddenWord.query.all()]

        if not forbidden_words:
            config.last_checked_submission_id = new_submissions[-1].id
            config.last_check_count = new_submissions_count
            db.session.commit()
            return {
                'alerts_created': 0,
                'new_submissions_count': new_submissions_count,
                'last_submission_id': config.last_checked_submission_id,
                'new_alerts': []
            }

        user_ids = {s.user_id for s in new_submissions if s.user_id}
        team_ids = {s.team_id for s in new_submissions if s.team_id}
        users = {u.id: u for u in Users.query.filter(Users.id.in_(user_ids)).all()} if user_ids else {}
        teams = {t.id: t for t in Teams.query.filter(Teams.id.in_(team_ids)).all()} if team_ids else {}

        submission_ids = [s.id for s in new_submissions]
        existing_keys = {
            (a.user_id, a.team_id, a.word, a.submission_id)
            for a in WordAlert.query.filter(WordAlert.submission_id.in_(submission_ids)).all()
        }

        alerts_created = 0
        new_alerts_data = []

        for submission in new_submissions:
            submitted_flag = submission.provided.lower() if submission.provided else ''
            for word in forbidden_words:
                if word in submitted_flag:
                    key = (submission.user_id, submission.team_id, word, submission.id)
                    if key not in existing_keys:
                        alert = WordAlert(
                            user_id=submission.user_id,
                            team_id=submission.team_id,
                            word=word,
                            submission_id=submission.id,
                            is_acknowledged=False
                        )
                        db.session.add(alert)
                        db.session.flush()
                        existing_keys.add(key)

                        user = users.get(submission.user_id)
                        team = teams.get(submission.team_id)

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

        config.last_checked_submission_id = new_submissions[-1].id
        config.last_check_count = new_submissions_count
        db.session.commit()

        return {
            'alerts_created': alerts_created,
            'new_submissions_count': new_submissions_count,
            'last_submission_id': config.last_checked_submission_id,
            'new_alerts': new_alerts_data
        }

    @plugin_bp.route('/admin/ctfd-canari-detection/api', methods=['POST'])
    @admins_only
    def api_actions():
        action = request.json.get('action')
        word = request.json.get('word')
        words = request.json.get('words')
        alert_id = request.json.get('alert_id')

        if action == 'add' and word:
            if not ForbiddenWord.query.filter_by(word=word).first():
                db.session.add(ForbiddenWord(word=word))
                db.session.commit()
                return jsonify({'success': True, 'message': f'Mot "{word}" ajouté avec succès!'})
            return jsonify({'success': False, 'message': f'Le mot "{word}" existe déjà!'})

        elif action == 'add_multiple' and words:
            existing_words_set = {w.word for w in ForbiddenWord.query.with_entities(ForbiddenWord.word).all()}
            added_words = []
            existing_words_found = []

            for w in words:
                w = w.strip()
                if not w:
                    continue
                if w not in existing_words_set:
                    db.session.add(ForbiddenWord(word=w))
                    added_words.append(w)
                    existing_words_set.add(w)
                else:
                    existing_words_found.append(w)

            db.session.commit()

            added_count = len(added_words)
            existing_count = len(existing_words_found)
            message = f'{added_count} mot(s) ajouté(s)'
            if existing_count:
                message += f', {existing_count} mot(s) déjà existant(s) ({", ".join(existing_words_found)})'

            return jsonify({
                'success': True,
                'message': message,
                'added_words': added_words,
                'added_count': added_count,
                'existing_count': existing_count,
                'existing_words': existing_words_found
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
            forbidden_words = [w.word.lower() for w in ForbiddenWord.query.all()]

            existing_keys = {
                (a.user_id, a.team_id, a.word, a.submission_id)
                for a in WordAlert.query.with_entities(
                    WordAlert.user_id, WordAlert.team_id, WordAlert.word, WordAlert.submission_id
                ).all()
            }

            total_submissions = 0
            alerts_created = 0
            last_id = 0

            while True:
                batch = Submissions.query.filter(
                    Submissions.type != 'pending',
                    Submissions.id > last_id
                ).order_by(Submissions.id.asc()).limit(BATCH_SIZE).all()

                if not batch:
                    break

                for submission in batch:
                    total_submissions += 1
                    submitted_flag = submission.provided.lower() if submission.provided else ''
                    for word in forbidden_words:
                        if word in submitted_flag:
                            key = (submission.user_id, submission.team_id, word, submission.id)
                            if key not in existing_keys:
                                db.session.add(WordAlert(
                                    user_id=submission.user_id,
                                    team_id=submission.team_id,
                                    word=word,
                                    submission_id=submission.id,
                                    is_acknowledged=False
                                ))
                                existing_keys.add(key)
                                alerts_created += 1

                last_id = batch[-1].id
                db.session.flush()

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f"Analyse complète : {alerts_created} alerte(s) créée(s)",
                'alerts_created': alerts_created,
                'total_submissions': total_submissions
            })

        return jsonify({'success': False, 'message': 'Action invalide'})

    @plugin_bp.route('/admin/ctfd-canari-detection', methods=['GET'])
    @admins_only
    def admin_panel():
        show_acknowledged = request.args.get('show_acknowledged', 'false') == 'true'

        forbidden_words = ForbiddenWord.query.all()

        alerts = (
            WordAlert.query
            .join(Submissions, WordAlert.submission_id == Submissions.id)
            .filter(
                WordAlert.is_acknowledged == show_acknowledged,
                Submissions.type != 'pending'
            )
            .options(
                joinedload(WordAlert.user),
                joinedload(WordAlert.team),
                joinedload(WordAlert.submission).joinedload('challenge')
            )
            .order_by(Submissions.date.desc())
            .all()
        )

        config = PluginConfig.query.first()

        return render_template(
            'alerts.html',
            forbidden_words=forbidden_words,
            alerts=alerts,
            show_acknowledged=show_acknowledged,
            last_submission_id=config.last_checked_submission_id if config else 0,
            last_check_count=config.last_check_count if config else 0
        )

    app.register_blueprint(plugin_bp)
