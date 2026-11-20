<?php
/**
 * Render the Newsup home strips below the menu on single posts.
 */

function aivision_article_header_strips() {
    if ( ! is_singular( 'post' ) || ! function_exists( 'newsup_get_option' )
        || ! function_exists( 'newsup_list_popular_taxonomies' )
        || ! function_exists( 'newsup_get_posts' ) ) {
        return;
    }

    newsup_list_popular_taxonomies(
        newsup_get_option( 'select_popular_tags_mode' ),
        newsup_get_option( 'show_popular_tags_title' ),
        newsup_get_option( 'number_of_popular_tags' )
    );

    if ( ! newsup_get_option( 'show_flash_news_section' ) ) {
        return;
    }

    $latest = newsup_get_posts(
        newsup_get_option( 'number_of_flash_news' ),
        newsup_get_option( 'select_flash_news_category' )
    );
    if ( ! $latest->posts ) {
        return;
    }

    $title = newsup_get_option( 'flash_news_title' );
    ?>
    <section class="mg-latest-news-sec">
        <div class="container-fluid">
            <div class="mg-latest-news">
                <div class="bn_title">
                    <h2 class="title"><?php if ( $title ) { echo esc_html( $title ); ?><span></span><?php } ?></h2>
                </div>
                <div class="mg-latest-news-slider marquee"<?php if ( is_rtl() ) { ?> data-direction="right" dir="ltr"<?php } ?>>
                    <?php foreach ( $latest->posts as $news_post ) { ?>
                        <a href="<?php echo esc_url( get_permalink( $news_post ) ); ?>">
                            <span><?php echo esc_html( get_the_title( $news_post ) ); ?></span>
                        </a>
                    <?php } ?>
                </div>
            </div>
        </div>
    </section>
    <?php
}

add_action( 'newsup_action_banner_exclusive_posts', 'aivision_article_header_strips', 5 );
