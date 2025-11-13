from django.urls import path
from .views import *

app_name = 'superuser'
urlpatterns = [

    # Home analytics
    path('', HomeView.as_view(), name='superuser'),
    # Users pages
    path('users/accounts/', UsersAccounts.as_view(), name='user_accounts'),
    path('users/<int:pk>/details/', UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/update-profile/', User_Accounts_Update_Profile.as_view(),
         name='user_accounts_update_profile'),
    path('users/<int:pk>/change-email/', User_Accounts_Change_Email.as_view(), name='user_accounts_change_email'),
    path('users/<int:pk>/update-role/', User_Accounts_Update_Role.as_view(), name='user_accounts_update_role'),
    path('users/<int:pk>/change-password/', User_Accounts_Change_Password.as_view(),
         name='user_accounts_change_password'),
    path('users/<int:pk>/update_status/', UserUpdateAccountStatusView.as_view(),
         name='user_update_account_status'),
    path('users/<int:pk>/delete/', User_Accounts_Delete_Account.as_view(), name='user_accounts_delete_account'),
    path('users/<int:pk>/modify-permission-groups/', User_Accounts_Modify_Permission_Groups.as_view(),
         name='user_accounts_modify_permission_groups'),

    path('users/add-new-user/', User_Accounts_AddNewUser.as_view(), name='user_accounts_add_new_user'),


    # Permissions urls
    path('users/permissions/', PermissionsUsers.as_view(), name='user_permissions'),
    path('users/permissions/add-new-group/', User_Permissions_AddNewGroup.as_view(),
         name='user_permissions_add_new_group'),
    path('users/permissions/delete-group/', User_Permissions_DeleteGroup.as_view(),
         name='user_permissions_delete_group'),
    path('users/permissions/<UID>/edit/', User_Permissions_EditGroup.as_view(), name='user_permissions_edit_group'),


    # Products urls
    path('products/list/', ProductsListView.as_view(), name='products_list'),
    path('products/add/', AddproductsView.as_view(), name='add_product'),
    path('products/edit/<int:pk>/', EditproductsView.as_view(), name='edit_product'),
    path('products/delete/<int:pk>/', DeleteProductView.as_view(), name='delete_product'),

    # categories urls
    path('categories/create/', CreateProductCategoryView.as_view(), name='create_category'),
    path('create-sub-category/', CreateProductSubCategoryView.as_view(), name='create_subcategory'),
    path('create-last-category/', CreateProductLastCategoryView.as_view(), name='create_lastcategory'),
    path('delete-product-image/<int:pk>/', DeleteProductImageView.as_view(), name='delete_product_image'),

    # AJAX category create
    path('ajax-categories/get/', AJAXGetCategoriesView.as_view(), name='AJAX_get_category'),
    path('ajax-categories/create/', AJAXCreateCategory.as_view(), name='AJAX_create_category'),
    path('ajax-sub-category/get/', get_subcategories, name='AJAX_get_subcategory'),
    path('ajax-sub-category/create/', AJAXCreateSubCategory.as_view(), name='AJAX_create_subcategory'),
    path('ajax-last-category/create/', AJAXCreateLastCategory.as_view(), name='AJAX_create_lastcategory'),

    # Orders Urls
    path('orders/list/', OrderListingView.as_view(), name='orders_list'),
    path('order/detail/<slug:order_id>/', OrderDetailesView.as_view(), name='orders_detail'),
    path('orders/delete/<int:pk>/', OrderDeleteView.as_view(), name='order_delete'),

    path('banner-list/', BannerListView.as_view(), name='banner_list'),
    path('banner-upload/', BannerCreateView.as_view(), name='banner_upload'),
    path('banner-edit/<int:pk>/', BannerUpdateView.as_view(), name='banner_edit'),

    path('rfq/', AdminRFQListView.as_view(), name='rfq_list'),
    path('rfq/<int:pk>/quote/', AdminQuotationUpdateView.as_view(), name='rfq_quote'),
    path('most-viewed-products/', AdminMostViewedProductsView.as_view(), name='view_product'),
   
    path('rating/', RatingView.as_view(), name='rating_list'),
    #notification
    path("notifications/", NotificationListView.as_view(), name="notifications_list"),
    path("notifications/add/", NotificationCreateView.as_view(), name="add_notification"),
    path('notifications/edit/<int:pk>/', EditNotificationView.as_view(), name='edit_notification'),
    path('notifications/delete/<int:pk>/', DeleteNotificationView.as_view(), name='delete_notification'),

    path('returns/', AdminReturnsView.as_view(), name='admin_returns'),
    path('returns/update/<str:return_serial>/', AdminReturnUpdateStatusView.as_view(), name='admin_returns_update_status'),
    # path('returns/refund/', StripeRefundView.as_view(), name='stripe_refund'),
    path('returns/delete/<str:return_serial>/', ReturnDeleteView.as_view(), name='admin_returns_delete'),

    path('returns/refund/', AdminProcessRefundView.as_view(), name='process_refund'),
    path('question/', AdminQuestionView.as_view(), name='question_list'),


    #category
    path("categories/", CategoryListView.as_view(), name="categories"),
    path('add-category/', CategoryCreateView.as_view(), name='add_category'),
    path('edit-category/', CategoryEditView.as_view(), name='edit_category'),
    path('delete-category/', CategoryDeleteView.as_view(), name='delete_category'),

    # Subcategory URLs
    path('subcategories/', CategorySubListView.as_view(), name='subcategory_list'),
    path('subcategories/<int:category_id>/', CategorySubListView.as_view(), name='category_subcategories'),
    path('add-subcategory/', SubCategoryCreateView.as_view(), name='add_subcategory'),
    path('edit-subcategory/', SubCategoryEditView.as_view(), name='edit_subcategory'),
    path('delete-subcategory/', SubCategoryDeleteView.as_view(), name='delete_subcategory'),
    path('edit-subcategory/<int:subcategory_id>/', SubCategoryEditView.as_view(), name='edit_subcategory_detail'),

    # Last Category URLs
    path('last-categories/<int:subcategory_id>/', SubCategoryLastListView.as_view(), name='lastcategory_list'),
    path('lastcategories/<int:subcategory_id>/', SubCategoryLastListView.as_view(), name='subcategory_lastcategories'),
    path('add-lastcategory/', LastCategoryCreateView.as_view(), name='add_lastcategory'),
    path('edit-lastcategory/', LastCategoryEditView.as_view(), name='edit_lastcategory'),
    path('delete-lastcategory/', LastCategoryDeleteView.as_view(), name='delete_lastcategory'),
    path('edit-lastcategory/<int:lastcategory_id>/', LastCategoryEditView.as_view(), name='edit_lastcategory_detail'),

    #Supplier Commission
    path('supplier-commission/', SupplierCommissionListView.as_view(), name='supplier_commission'),
    path('supplier-commission/edit/', SupplierCommissionEditView.as_view(), name='supplier_commission_edit'),
    path('supplier-commission/delete/', SupplierCommissionDeleteView.as_view(), name='supplier_commission_delete'),

    #vacationmode
    path('vacation-mode/', AdminVacationModeView.as_view(), name='admin_vacation_mode'),

    #Top supplier
     path('add-to-supplier/', AddTopSupplierView.as_view(), name='add_to_supplier'),
     path('top-supplier-list/', TopSupplierListView.as_view(), name='topsupplierlist'),
     path('edit-top-supplier/', EditTopSupplierView.as_view(), name='edit_top_supplier'),
     path('delete-top-supplier/', DeleteTopSupplierView.as_view(), name='delete_top_supplier'),

     #Marketing tools

     #coupons
    path('coupons/', CouponView.as_view(), name='coupons'),
    path('edit-coupon/', edit_coupon, name='edit_coupon'),
    path('delete-coupon/',delete_coupon, name='delete_coupon'),
    path('coupon/<int:coupon_id>/details/', coupon_details, name='coupon_details'),
     path('buyxgety/', BuyXGetYPromotionView.as_view(), name='buyxgety_promotion'),
     path('buyxgety/add/', AddPromotionView.as_view(), name='add_promotion'),
     path('buyxgety/edit/<int:pk>/', EditPromotionView.as_view(), name='edit_promotion'),
     path('buyxgety/delete/<int:pk>/', delete_promotion, name='delete_promotion'),

     path('buyxgifty/',BuyXGiftYPromotionView.as_view(),name='buyxgift_promotion'),
     path('buyxgifty/add/', AddGiftPromotionView.as_view(), name='add_gift_promotion'),
     path('buyxgifty/edit/<int:pk>/', EditGiftPromotionView.as_view(), name='edit_gift_promotion'),
     path('buyxgifty/delete/<int:pk>/', delete_gift_promotion, name='delete_gift_promotion'),

     path('basketpromotion/', BasketPromotionView.as_view(), name='basket_promotion'),
     path('basketpromotion/add/', AddBasketPromotionView.as_view(),name='add_basket_promotion'),
     path('basketpromotion/edit/<int:pk>/', EditBasketPromotionView.as_view(), name='edit_basket_promotion'),
     path('basketpromotion/delete/<int:pk>/', delete_basket_promotion,name='delete_basket_promotion'),

     #settings
   
    #bank
     path("banks/", BankView.as_view(), name="banks"),
     path("banks/add/", AddBankView.as_view(), name="bank_add"),
     path("banks/get/<int:pk>/", GetBankView.as_view(), name="bank_get"),
     path("banks/edit/<int:pk>/", EditBankView.as_view(), name="bank_edit"),
     path("banks/delete/<int:pk>/", DeleteBankView.as_view(), name="bank_delete"),
    #origincountry
     path("origin-country/", OriginCountryView.as_view(), name="origin_country"),
     path("origin-country/add/", add_origin_country, name="add_origin_country"),
     path("origin-country/edit/<int:pk>/", edit_origin_country, name="edit_origin_country"),
     path("origin-country/delete/<int:pk>/", delete_origin_country, name="delete_origin_country"),
    #country
     path("country/", CountryView.as_view(), name="countrys"),
     path("country/add/", CountryAddView.as_view(), name="origin_country_add"),
     path("country/edit/<int:cid>/", CountryEditView.as_view(), name="origin_country_edit"),
     path("country/delete/<int:cid>/", CountryDeleteView.as_view(), name="origin_country_delete"),
    #region
     path('region/', RegionView.as_view(), name='region'),
     path('region/add/', RegionAddView.as_view(), name='region_add'),
     path('region/edit/<int:pk>/', RegionEditView.as_view(), name='region_edit'),
     path('region/delete/<int:pk>/', RegionDeleteView.as_view(), name='region_delete'),
     #cities
     path("cities/", CityListView.as_view(), name="cities_list"),
     path("cities/add/", CityCreateView.as_view(), name="add_city"),
     path("cities/edit/<int:pk>/", CityUpdateView.as_view(), name="edit_city"),
     path("cities/delete/<int:pk>/", CityDeleteView.as_view(), name="delete_city"),
     #currency
     path("currency/", CurrencyView.as_view(), name="currency"),
     path("currency/add/", add_currency, name="add_currency"),
     path("currency/edit/<int:cid>/", add_currency, name="edit_currency"),
     path("currency/delete/<int:pk>/", delete_currency, name="delete_currency"),
     #returnreson
     path("return-reason/", ReturnReasonView.as_view(), name="return_reason"),
     path("return-reason/add/", add_return_reason, name="add_return_reason"),
     path("return-reason/edit/<int:pk>/", edit_return_reason, name="edit_return_reason"),
     path("return-reason/delete/<int:pk>/", delete_return_reason, name="delete_return_reason"),
     #department
     path("department/", DepartmentView.as_view(), name="department"),
     path("department/add/", add_department, name="add_department"),
     path("department/edit/<int:pk>/", edit_department, name="edit_department"),
     path("department/delete/<int:pk>/", delete_department, name="delete_department"),
     #suppliertype
     path("suppliertype/", SupplierTypeView.as_view(), name="suppliertype"),
     path("suppliertype/add/", add_supplier_type, name="add_supplier_type"),
     path("suppliertype/edit/<int:pk>/", edit_supplier_type, name="edit_supplier_type"),
     path("suppliertype/delete/<int:pk>/", delete_supplier_type, name="delete_supplier_type"),
     #addresstype
     path("addresstype/", AddressTypeView.as_view(), name="addresstype"),
     path("addresstype/add/", add_address_type, name="add_address_type"),
     path("addresstype/edit/<int:pk>/", edit_address_type, name="edit_address_type"),
     path("addresstype/delete/<int:pk>/", delete_address_type, name="delete_address_type"),
     #unit
     path('unit/', UnitView.as_view(), name='unit'),
     path('unit/add/', AddUnitView.as_view(), name='add_unit'),
     path('unit/edit/<int:id>/', EditUnitView.as_view(), name='edit_unit'),
     path('unit/delete/<int:id>/', DeleteUnitView.as_view(), name='delete_unit'),
     #deliverytime
     path('deliverytime/', DeliveryTimeView.as_view(), name='deliverytime'),
     path('deliverytime/add/', DeliveryTimeAddView.as_view(), name='deliverytime_add'),
     path('deliverytime/edit/<int:pk>/', DeliveryTimeEditView.as_view(), name='deliverytime_edit'),
     path('deliverytime/delete/<int:pk>/', DeliveryTimeDeleteView.as_view(), name='deliverytime_delete'),
     #returntime
     path('returntime/', ReturnTimeView.as_view(), name='returntime'),
     path('returntime/add/', ReturnTimeAddView.as_view(), name='returntime_add'),
     path('returntime/edit/<int:pk>/', ReturnTimeEditView.as_view(), name='returntime_edit'),
     path('returntime/delete/<int:pk>/', ReturnTimeDeleteView.as_view(), name='returntime_delete'),
     #standingtime
     path('standingtime/', StandingTimeView.as_view(), name='standingtime'),
     path('standingtime/add/', StandigTimeAddView.as_view(), name='standingtime_add'),
     path('standingtime/edit/<int:pk>/', StandingTimeEditView.as_view(), name='standingtime_edit'),
     path('standingtime/delete/<int:pk>/', StandingTimeDeleteView.as_view(), name='standingtime_delete'),
     #warrantry
     path('warranty/', WarrantyView.as_view(), name='warranty'),
     path('warranty/add/', AddWarrantyView.as_view(), name='warranty_add'),
     path('warranty/edit/<int:pk>/', EditWarrantyView.as_view(), name='warranty_edit'),
     path('warranty/delete/<int:pk>/', DeleteWarrantyView.as_view(), name='warranty_delete'),
     # Splash Screen List
     path('splash/', SplashScreenView.as_view(), name='splash_screen'),
     path('splash/add/', SplashScreenAddView.as_view(), name='add_splash_screen'),
     path('splash/edit/<int:pk>/', SplashScreenEditView.as_view(), name='edit_splash_screen'),
     path('splash/delete/<int:pk>/', SplashScreenDeleteView.as_view(), name='delete_splash_screen'),
     #Static contents
     path('standing-time/', StaticcontentsView.as_view(), name='standing_time'),
     path('standing-time/add/', AddStaticcontentView.as_view(), name='add_staticcontent'),
     path('standing-time/edit/<int:pk>/', EditStaticcontentView.as_view(), name='edit_staticcontent'),
     path('standing-time/delete/<int:pk>/', DeleteStaticcontentView.as_view(), name='delete_staticcontent'),
     #Social Links
     path("social-links/", SocialLinksView.as_view(), name="social_links"),
     path("social-links/add/", AddSocialLinkView.as_view(), name="add_social_link"),
     path("social-links/edit/<int:pk>/", EditSocialLinkView.as_view(), name="edit_social_link"),
     path("social-links/delete/<int:pk>/", DeleteSocialLinkView.as_view(), name="delete_social_link"),
     #Faqs
     path('faq/', FaqView.as_view(), name='faq'),
     path('faq/add/', AddFaqView.as_view(), name='add_faq'),
     path('faq/edit/<int:pk>/', EditFaqView.as_view(), name='edit_faq'),
     path('faq/delete/<int:pk>/', DeleteFaqView.as_view(), name='delete_faq'),
     #Admins List
     path('admin-list/', AdminListView.as_view(), name='admin_list'),
     path('admin-list/add/', AddAdminView.as_view(), name='add_admin'),
     path('admin-list/edit/<int:pk>/', EditAdminView.as_view(), name='edit_admin'),
     path('admin-list/delete/<int:pk>/', DeleteAdminView.as_view(), name='delete_admin'),
     #Site Messages
     path('site-messages/', SiteMessagesView.as_view(), name='site_messages'),
     path('site-messages/delete/<int:pk>/', ContactDeleteView.as_view(), name='contact_delete'),
     #Dynamic input 
     path('dynamic-inputs/', DynamicInputListView.as_view(), name='dynamic_inputs'),
     path('dynamic-inputs/add/', DynamicInputAddView.as_view(), name='dynamic_input_add'),
     path('dynamic-inputs/edit/<int:pk>/', DynamicInputEditView.as_view(), name='dynamic_input_edit'),
     path('dynamic-inputs/delete/<int:pk>/', DynamicInputDeleteView.as_view(), name='dynamic_input_delete'),

     path('form-controls/', FormControlsView.as_view(), name='form_controls'),

     
]





  




 
     




     


