from flask import Blueprint, render_template, request, redirect, flash,session
from firebase_admin import auth
from firebase import firestore_db
from flask import session
auth_bp = Blueprint("auth", __name__)
import requests


@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        
        if password != confirm_password:
            return "Passwords do not match."

        try:

            # Create user in Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password,
                display_name=fullname
            )

            # Save user profile in Firestore
            firestore_db.collection("farmers").document(user.uid).set({
                "uid": user.uid,
                "fullname": fullname,
                "email": email,
                "mobile": mobile
            })

            flash("Account created successfully! Please login.")
            return redirect("/login")

        except Exception as e:
            return f"Error: {e}"

    return render_template("register.html")

