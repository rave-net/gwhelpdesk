from django.urls import re_path

from helpdesk import views



urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^index/$', views.index, name='index'),
    re_path(r'^login/$', views.login, name='login'),
    re_path(r'^logout/$', views.logout, name='logout'),
    re_path(r'^gwconfig/$', views.gwconfig, name='gwconfig'),
    #url(r'^configerror/$', views.configerror, name='configerror'),
    re_path(r'^admins/$', views.admins, name='admins'),
    re_path(r'^changepassword/$', views.changepassword, name='changepassword'),
    re_path(r'^changeadminpassword/$', views.changeadminpassword, name='changeadminpassword'),
    re_path(r'^addadmin/$', views.addadmin, name='addadmin'),
    re_path(r'^search/$', views.search, name='search'),
    re_path(r'^searchresults/$', views.searchresults, name='searchresults'),
    re_path(r'^userdata/$', views.userdata, name='userdata'),
    re_path(r'^extuserdata/$', views.extuserdata, name='extuserdata'),
    re_path(r'^groups/$', views.groups, name='groups'),
    re_path(r'^addgroup/$', views.addgroup, name='addgroup'),
    re_path(r'^groupdetails/$', views.groupdetails, name='groupdetails'),
    re_path(r'^groupsearch/$', views.groupsearch, name='groupsearch'),
    re_path(r'^groupsearchresults/$', views.groupsearchresults, name='groupsearchresults'),
    re_path(r'^grouplist/$', views.grouplist, name='grouplist'),
    re_path(r'^addgrpmember/$', views.addgrpmember, name='addgrpmember'),
    re_path(r'^move/$', views.move, name='move'),
    re_path(r'^maintenance/$', views.maintenance, name='maintenance'),
    re_path(r'^addtogroups/$', views.addtogroups, name='addtogroups'),
    re_path(r'^adduser/$', views.adduser, name='adduser'),
    re_path(r'^addextuser/$', views.addextuser, name='addextuser'),
    re_path(r'^deluser/$', views.deluser, name='deluser'),
    re_path(r'^userlist/$', views.userlist, name='userlist'),
    re_path(r'^extuserlist/$', views.extuserlist, name='extuserlist'),
    re_path(r'^rename/$', views.rename, name='rename'),
    re_path(r'^dissociate/$', views.dissociate, name='dissociate'),
    re_path(r'^viewlog/$', views.viewlog, name='viewlog'),
    re_path(r'^nicknames/$', views.nicknames, name='nicknames'),
    re_path(r'^addnickname/$', views.addnickname, name='addnickname'),
    re_path(r'^resources/$', views.resources, name='resources'),
    re_path(r'^addresource/$', views.addresource, name='addresource'),



]
