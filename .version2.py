from os import system

message = input("Enter commit message: ")
system(f"git add .; git commit -m '{message}'; git pull origin version2; git push origin version2")
system("git remote rm origin")
system("git remote add origin https://github.com/slojar/citbank.git")
print("Switched to Github REPO!!!")
system("git push origin version2; git push heroku version2:master")
print("Push to GITHUB and HEROKU complete!!!")
system("git remote rm origin")
system("git remote add origin https://gitlab.com/tm30/cit-bank-user-management-backend.git")
print("Switched Back to TM30 Gitlab")

