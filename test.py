import os

path=[]
path.append("./css")
path.append("./css/bootstrap")
path.append("./css/css")
path.append("./css/css/mixins")
path.append("./fonts")
path.append("./fonts/flaticon")
path.append("./fonts/flaticon/font")
path.append("./fonts/flaticon/license")
path.append("./fonts/icomoon")
path.append("./fonts/ionicons")
path.append("./fonts/ionicons/css")
path.append("./fonts/ionicons/fonts")
path.append("./fonts/open-iconic")
path.append("./images")
path.append("./images/profile_photo")
path.append("./js")
path.append("./scss")
path.append("./scss/bootstrap")
path.append("./scss/bootstrap/mixins")
path.append("./scss/bootstrap/utilities")

for i in path:
    os.makedirs(i)