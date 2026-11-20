<?php
/** Link to AI Vision's Telegram channel under the Newsup navigation. */

function aivision_telegram_offers_banner() {
    ?>
    <aside class="aiv-telegram-offers" aria-label="Offerte AI Vision su Telegram">
        <div class="container-fluid">
            <div class="aiv-telegram-offers-inner">
                <i class="fab fa-telegram-plane" aria-hidden="true"></i>
                <div class="aiv-telegram-offers-copy">
                    <strong>Offerte AI Vision</strong>
                    <span>La nostra selezione di offerte Amazon</span>
                </div>
                <a href="https://t.me/aivision_tech">Segui su Telegram</a>
            </div>
        </div>
    </aside>
    <script id="aivision-telegram-placement">
    (() => {
        // Newsup renders its Top Tags before the banner hook on the home page.
        const banner = document.currentScript.previousElementSibling;
        const header = banner.parentElement.querySelector(':scope > header.mg-headwidget');
        if (header) {
            const next = header.nextElementSibling;
            const anchor = next && next.classList.contains('clearfix') ? next : header;
            if (anchor.nextElementSibling !== banner) {
                anchor.after(banner);
            }
        }
    })();
    </script>
    <?php
}

function aivision_telegram_offers_styles() {
    wp_register_style( 'aivision-telegram-offers', false, array( 'newsup-style' ) );
    wp_enqueue_style( 'aivision-telegram-offers' );
    wp_add_inline_style( 'aivision-telegram-offers', <<<'CSS'
.aiv-telegram-offers {
    background: #eef5ff;
    border-bottom: 1px solid #d5e3fa;
    color: #12305a;
}
.aiv-telegram-offers-inner {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 56px;
    padding: 7px 0;
}
.aiv-telegram-offers-inner > i {
    display: grid;
    place-items: center;
    flex: 0 0 36px;
    height: 36px;
    border-radius: 50%;
    background: #d9e9ff;
    color: #1550b3;
    font-size: 20px;
}
.aiv-telegram-offers-copy {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 16px;
    line-height: 1.25;
}
.aiv-telegram-offers-copy strong { font-size: 16px; }
.aiv-telegram-offers-copy span { font-size: 14px; }
.aiv-telegram-offers-inner > a {
    flex-shrink: 0;
    margin-inline-start: auto;
    padding: 10px 14px;
    border-radius: 7px;
    background: #124ec3;
    color: #fff;
    font-size: 14px;
    font-weight: 700;
    line-height: 1.25;
    text-decoration: none;
}
.aiv-telegram-offers-inner > a:hover,
.aiv-telegram-offers-inner > a:focus-visible {
    background: #0d3689;
    color: #fff;
}
.aiv-telegram-offers-inner > a:focus-visible {
    outline: 2px solid #12305a;
    outline-offset: 2px;
}
@media (max-width: 575px) {
    .aiv-telegram-offers-inner { gap: 8px; }
    .aiv-telegram-offers-inner > i { flex-basis: 28px; height: 28px; font-size: 16px; }
    .aiv-telegram-offers-copy span { display: none; }
    .aiv-telegram-offers-inner > a { padding-inline: 9px; font-size: 13px; }
}
CSS
    );
}

function aivision_mount_telegram_offers() {
    if ( 'newsup' === get_template() ) {
        add_action( 'newsup_action_banner_exclusive_posts', 'aivision_telegram_offers_banner', 1 );
        add_action( 'wp_enqueue_scripts', 'aivision_telegram_offers_styles', 30 );
    }
}
add_action( 'wp', 'aivision_mount_telegram_offers', 20 );
