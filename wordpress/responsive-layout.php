<?php
/** Improve Newsup reading layouts around AlterVista's native ad slots. */

function aivision_responsive_layout_styles() {
    if ( 'newsup' !== get_template() ) {
        return;
    }
    wp_register_style( 'aivision-responsive-layout', false, array( 'newsup-style' ) );
    wp_enqueue_style( 'aivision-responsive-layout' );
    wp_add_inline_style( 'aivision-responsive-layout', <<<'CSS'
/* AlterVista supplies the visible masthead when the theme branding is hidden. */
body:has(> .av-header a) .mg-nav-widget-area-back:has(.site-branding-text.d-none):not(:has(.site-logo a, iframe, av-adv-slot)) {
    display: none;
}

.av-adv-header-slot-container { margin-top: clamp(12px, 1.5vw, 20px) !important; }
main.single-class { padding-top: clamp(18px, 2.5vw, 36px); }

.single-class article.page-content-single > :is(p, ul, ol, blockquote) {
    max-inline-size: 72ch;
    font-size: clamp(16px, 14px + .3vw, 18px);
    line-height: 1.7;
    overflow-wrap: anywhere;
}
.single-class article.page-content-single .wp-block-table { overflow-x: auto; }

@media (min-width: 992px) {
    .mg-menu-full #menu-menu-principale > li > a {
        padding-inline: clamp(8px, 4.7vw - 45px, 22px);
    }
    :is(#content > .row, #content > .container-fluid > .row):has(> aside.col-md-4) > .col-md-8 {
        flex: 1 1 0;
        max-width: none;
        min-width: 0;
    }
    :is(#content > .row, #content > .container-fluid > .row) > aside.col-md-4 {
        min-width: 330px;
    }
}

@media (min-width: 992px) and (max-width: 1199.98px) {
    .mg-menu-full #menu-menu-principale > li > a { font-size: 13px; letter-spacing: normal; }
}

@media (max-width: 991.98px) {
    .mg-headwidget > .mg-head-detail { display: none; }
    .mg-headwidget .navbar-toggler { min-width: 44px; min-height: 44px; }
    .aiv-telegram-offers .aiv-telegram-offers-inner > a {
        display: inline-flex;
        align-items: center;
        min-height: 44px;
    }
}

@media (min-width: 768px) and (max-width: 991.98px) {
    :is(#content > .row, #content > .container-fluid > .row) > :is(.col-md-8, aside.col-md-4) {
        flex: 0 0 100%;
        max-width: 100%;
    }
    #content #sidebar-right { max-width: 560px; margin-inline: auto; }
}

@media (max-width: 767.98px) {
    .mg-tpt-tag-area .mg-tpt-txnlst {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .mg-tpt-tag-area .mg-tpt-txnlst > strong { flex: none; white-space: nowrap; }
    .mg-tpt-tag-area .mg-tpt-txnlst > ul {
        display: flex;
        gap: 6px;
        min-width: 0;
        overflow-x: auto;
        scrollbar-width: thin;
    }
    .mg-tpt-tag-area .mg-tpt-txnlst li { flex: none; margin: 0; white-space: nowrap; }
    .mg-tpt-tag-area .mg-tpt-txnlst a { display: block; padding: 4px 6px; }
    .single-class .mg-blog-post-box > :is(.mg-header, article.page-content-single) {
        padding-inline: clamp(15px, 4vw, 24px);
    }
    .single-class .mg-blog-post-box .mg-header h1 {
        font-size: clamp(26px, 5.6vw, 32px);
        line-height: 1.25;
        overflow-wrap: anywhere;
    }
    .home .mg-fea-area .homemain .mg-blog-post.lg {
        height: clamp(260px, 74vw, 340px);
        min-height: 0;
    }
}

@media (max-width: 329.98px) {
    :is(#content > .row, #content > .container-fluid > .row) > aside.col-md-4 {
        padding-inline: 10px;
    }
}
CSS
    );
}
add_action( 'wp_enqueue_scripts', 'aivision_responsive_layout_styles', 35 );
