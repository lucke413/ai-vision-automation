<?php
/**
 * Keep Newsup related-post titles below their featured images.
 */

function aivision_related_card_styles() {
    if ( ! is_singular( 'post' ) || 'newsup' !== get_template() ) {
        return;
    }

    wp_register_style( 'aivision-related-cards', false, array( 'newsup-style' ) );
    wp_enqueue_style( 'aivision-related-cards' );
    wp_add_inline_style( 'aivision-related-cards', <<<'CSS'
.single-class .mg-featured-slider > .row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: clamp(12px, 1.6vw, 24px);
    margin: 0;
}

.single-class .mg-featured-slider > .row > .col-md-4 {
    display: flex;
    min-width: 0;
    max-width: none;
    padding: 0;
    margin: 0;
}

.single-class .mg-featured-slider .mg-blog-post-3.minh {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: auto;
    margin: 0 !important;
    border: 1px solid #dfe5ee;
    border-radius: 8px;
    background-color: #fff;
    background-size: 0 0;
}

.single-class .mg-featured-slider .mg-blog-post-3[style*="background-image"]::before {
    content: "";
    display: block;
    flex: none;
    width: 100%;
    aspect-ratio: 16 / 10;
    background-color: #edf1f6;
    background-image: inherit;
    background-position: center;
    background-repeat: no-repeat;
    background-size: contain;
}

.single-class .mg-featured-slider .mg-blog-post-3 .mg-blog-inner {
    position: static;
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    background: #fff;
}

.single-class .mg-featured-slider .mg-blog-inner h4.title {
    display: block;
    margin: 0;
    overflow: visible;
    overflow-wrap: anywhere;
    -webkit-line-clamp: unset;
    line-clamp: none;
    font-size: clamp(1rem, 1.35vw, 1.2rem);
    line-height: 1.35;
}

.single-class .mg-featured-slider .mg-blog-inner h4.title a {
    color: #17233a;
}

.single-class .mg-featured-slider .mg-blog-inner h4.title a:is(:hover, :focus-visible) {
    color: var(--pri-color, #1151d3);
    text-decoration: underline;
}

.single-class .mg-featured-slider .mg-blog-inner .mg-blog-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    margin-top: auto;
    padding-top: 4px;
}

.single-class .mg-featured-slider .mg-blog-inner .mg-blog-meta :is(.mg-blog-date, a, i) {
    color: #46536a;
}

@media (max-width: 767.98px) {
    .single-class .mg-featured-slider > .row {
        grid-template-columns: minmax(0, 1fr);
    }
}
CSS
    );
}

add_action( 'wp_enqueue_scripts', 'aivision_related_card_styles', 30 );
