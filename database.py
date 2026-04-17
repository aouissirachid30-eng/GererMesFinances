# database.py
from models import db, Monnaie, Compte, Transaction
from datetime import datetime

# ==========================================
# INITIALISER LA BASE DE DONNÉES
# ==========================================
def initialiser_base(app):
    with app.app_context():
        db.create_all()
        
        # Créer les monnaies par défaut si elles n'existent pas
        if Monnaie.query.count() == 0:
            dzd = Monnaie(code_monnaie='DZD', symbole='د.ج', nom='Dinar Algérien')
            eur = Monnaie(code_monnaie='EUR', symbole='€', nom='Euro')
            usd = Monnaie(code_monnaie='USD', symbole='$', nom='Dollar US')
            
            db.session.add(dzd)
            db.session.add(eur)
            db.session.add(usd)
            db.session.commit()
            print("✅ Monnaies initialisées")

# ==========================================
# CRÉER UN COMPTE
# ==========================================
def creer_compte(nom_compte, type_compte, solde_initial, code_monnaie='DZD'):
    monnaie = Monnaie.query.filter_by(code_monnaie=code_monnaie).first()
    
    if not monnaie:
        return None, "Monnaie introuvable"
    
    compte = Compte(
        nom_compte=nom_compte,
        type_compte=type_compte,
        solde_initial=solde_initial,
        solde_final=solde_initial,
        id_monnaie=monnaie.id_monnaie
    )
    
    db.session.add(compte)
    db.session.commit()
    
    return compte, "Compte créé avec succès"

# ==========================================
# CRÉER UNE TRANSACTION
# ==========================================
def creer_transaction(id_compte, date_transaction, categorie, moyen_paiement, 
                     designation, montant_encaissement=0.0, montant_decaissement=0.0):
    
    compte = Compte.query.get(id_compte)
    
    if not compte:
        return None, "Compte introuvable"
    
    # VALIDATION : Si Revenu, bloquer décaissement
    if categorie == "Revenu" and montant_decaissement > 0:
        return None, "Un revenu ne peut pas avoir de montant décaissement"
    
    # VALIDATION : Si Dépense, bloquer encaissement
    if categorie in ["Dépense fixe", "Dépense variable"] and montant_encaissement > 0:
        return None, "Une dépense ne peut pas avoir de montant encaissement"
    
    # Calculer le mois et l'année
    mois = date_transaction.month
    annee = date_transaction.year
    
    # Calculer le solde cumulé
    derniere_transaction = Transaction.query.filter_by(id_compte=id_compte).order_by(Transaction.id_transaction.desc()).first()
    
    if derniere_transaction:
        solde_cumule = derniere_transaction.solde_cumule + montant_encaissement - montant_decaissement
    else:
        solde_cumule = compte.solde_initial + montant_encaissement - montant_decaissement
    
    # Créer la transaction
    transaction = Transaction(
        date_transaction=date_transaction,
        mois=mois,
        annee=annee,
        id_compte=id_compte,
        categorie=categorie,
        moyen_paiement=moyen_paiement,
        designation=designation,
        montant_encaissement=montant_encaissement,
        montant_decaissement=montant_decaissement,
        solde_cumule=solde_cumule
    )
    
    db.session.add(transaction)
    
    # Mettre à jour le compte
    compte.total_encaissement += montant_encaissement
    compte.total_decaissement += montant_decaissement
    compte.calculer_solde()
    
    db.session.commit()
    
    return transaction, "Transaction créée avec succès"

# ==========================================
# OBTENIR TOUS LES COMPTES
# ==========================================
def obtenir_comptes():
    return Compte.query.filter_by(actif=True).all()

# ==========================================
# OBTENIR TRANSACTIONS PAR COMPTE
# ==========================================
def obtenir_transactions(id_compte):
    return Transaction.query.filter_by(id_compte=id_compte).order_by(Transaction.date_transaction.desc()).all()

# ==========================================
# OBTENIR STATISTIQUES
# ==========================================
def obtenir_statistiques(id_compte, mois=None, annee=None):
    query = Transaction.query.filter_by(id_compte=id_compte)
    
    if mois:
        query = query.filter_by(mois=mois)
    if annee:
        query = query.filter_by(annee=annee)
    
    transactions = query.all()
    
    stats = {
        'total_revenus': sum(t.montant_encaissement for t in transactions if t.categorie == "Revenu"),
        'total_depenses_fixes': sum(t.montant_decaissement for t in transactions if t.categorie == "Dépense fixe"),
        'total_depenses_variables': sum(t.montant_decaissement for t in transactions if t.categorie == "Dépense variable"),
        'total_virement_enc': sum(t.montant_encaissement for t in transactions if t.moyen_paiement == "Virement"),
        'total_virement_dec': sum(t.montant_decaissement for t in transactions if t.moyen_paiement == "Virement"),
        'total_especes_enc': sum(t.montant_encaissement for t in transactions if t.moyen_paiement == "Espèces"),
        'total_especes_dec': sum(t.montant_decaissement for t in transactions if t.moyen_paiement == "Espèces"),
        'total_carte_enc': sum(t.montant_encaissement for t in transactions if t.moyen_paiement == "Carte bancaire"),
        'total_carte_dec': sum(t.montant_decaissement for t in transactions if t.moyen_paiement == "Carte bancaire"),
    }
    
    return stats