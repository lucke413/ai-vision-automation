<?php
/** Newsup reading lists, ranked by the site's existing Jetpack view data. */

function aivision_reading_view_ids( $days ) {
    $key = 'aivision_reading_views_' . $days;
    $cached = get_transient( $key );
    if ( false !== $cached ) {
        return $cached;
    }

    $ids = array();
    if ( class_exists( '\\Automattic\\Jetpack\\Stats\\WPCOM_Stats' ) ) {
        try {
            $stats = new \Automattic\Jetpack\Stats\WPCOM_Stats();
            $result = $stats->convert_stats_array_to_object(
                $stats->get_top_posts( array( 'max' => 20, 'summarize' => 1, 'num' => $days ) )
            );
            $rows = $result->summary->postviews ?? array();
            $ids = array_values( array_unique( array_filter( array_map( 'absint', wp_list_pluck( $rows, 'id' ) ) ) ) );
        } catch ( Throwable $error ) {
            // Keep the reading widget available during a stats service outage.
        }
    }
    set_transient( $key, $ids, ( $ids ? 30 : 5 ) * MINUTE_IN_SECONDS );
    return $ids;
}

function aivision_reading_lists() {
    $current = is_singular( 'post' ) ? get_queried_object_id() : 0;
    $query = array(
        'post_type' => 'post',
        'post_status' => 'publish',
        'has_password' => false,
        'posts_per_page' => 4,
        'ignore_sticky_posts' => true,
        'no_found_rows' => true,
    );
    $lists = array();
    foreach ( array( 'trend' => array( 'Di tendenza', 2 ), 'popular' => array( 'Più letti', 7 ) ) as $key => $period ) {
        list( $label, $days ) = $period;
        $ids = array_values( array_diff( aivision_reading_view_ids( $days ), array( $current ) ) );
        if ( $ids ) {
            $posts = get_posts( $query + array( 'post__in' => $ids, 'orderby' => 'post__in' ) );
            if ( $posts ) {
                $lists[ $key ] = array( $label, 'Letture degli ultimi ' . $days . ' giorni', $posts );
            }
        }
    }
    if ( ! $lists ) {
        $discussed = get_posts( $query + array(
            'post__not_in' => array( $current ),
            'date_query' => array( array( 'after' => '30 days ago' ) ),
            'comment_count' => array( 'value' => 0, 'compare' => '>' ),
            'orderby' => array( 'comment_count' => 'DESC', 'date' => 'DESC' ),
        ) );
        if ( $discussed ) {
            $lists['popular'] = array( 'Più discussi', 'Commenti agli articoli degli ultimi 30 giorni', $discussed );
        }
    }
    $latest = get_posts( $query + array( 'post__not_in' => array( $current ) ) );
    if ( $latest ) {
        $lists['latest'] = array( 'Ultimi', '', $latest );
    }
    return $lists;
}

function aivision_render_reading_widget() {
    $lists = aivision_reading_lists();
    if ( ! $lists ) {
        return;
    }
    $id = wp_unique_id( 'aiv-reading-' );
    $default = array_key_first( $lists );
    ?>
    <section class="aiv-reading" aria-labelledby="<?php echo esc_attr( $id ); ?>-title">
        <h2 id="<?php echo esc_attr( $id ); ?>-title">Da leggere</h2>
        <div class="aiv-reading-switch" role="group" aria-label="Scegli la classifica degli articoli">
            <?php foreach ( $lists as $key => $list ) : ?>
                <input class="aiv-reading-choice" type="radio" name="<?php echo esc_attr( $id ); ?>"
                       id="<?php echo esc_attr( $id . '-' . $key ); ?>" data-view="<?php echo esc_attr( $key ); ?>"
                       <?php checked( $key, $default ); ?>>
            <?php endforeach; ?>
            <div class="aiv-reading-labels">
                <?php foreach ( $lists as $key => $list ) : ?>
                    <label for="<?php echo esc_attr( $id . '-' . $key ); ?>" data-view="<?php echo esc_attr( $key ); ?>"><?php echo esc_html( $list[0] ); ?></label>
                <?php endforeach; ?>
            </div>
            <?php foreach ( $lists as $key => $list ) : ?>
                <div class="aiv-reading-panel" data-view="<?php echo esc_attr( $key ); ?>">
                    <?php if ( $list[1] ) : ?>
                        <p class="aiv-reading-period"><?php echo esc_html( $list[1] ); ?></p>
                    <?php endif; ?>
                    <ul>
                        <?php foreach ( $list[2] as $entry ) : ?>
                            <li>
                                <a href="<?php echo esc_url( get_permalink( $entry ) ); ?>">
                                    <span class="aiv-reading-thumb" aria-hidden="true">
                                        <?php echo get_the_post_thumbnail( $entry, 'thumbnail', array( 'alt' => '', 'loading' => 'lazy', 'decoding' => 'async' ) ); ?>
                                    </span>
                                    <span class="aiv-reading-title"><?php echo esc_html( get_the_title( $entry ) ); ?></span>
                                </a>
                            </li>
                        <?php endforeach; ?>
                    </ul>
                </div>
            <?php endforeach; ?>
        </div>
    </section>
    <?php
}

function aivision_reading_language() {
    $page_url = is_singular( 'post' ) ? get_permalink( get_queried_object_id() ) : home_url( '/' );
    $languages = array(
        'en' => 'English',
        'fr' => 'Français',
        'de' => 'Deutsch',
        'es' => 'Español',
        'pt' => 'Português',
        'nl' => 'Nederlands',
        'pl' => 'Polski',
        'ro' => 'Română',
    );
    ?>
    <details class="aiv-language notranslate" translate="no">
        <summary>
            <i class="fas fa-globe" aria-hidden="true"></i>
            <span>Lingua <span class="aiv-language-alt" lang="en">/ Language</span></span>
        </summary>
        <ul>
            <li><a href="<?php echo esc_url( $page_url ); ?>" lang="it" hreflang="it"
                   data-original="<?php echo esc_url( $page_url ); ?>"
                   onclick="if (this.origin !== location.origin || this.href !== this.dataset.original) { location.assign(this.dataset.original); return false; }">Italiano</a></li>
            <?php foreach ( $languages as $code => $language ) :
                $translate_url = 'https://translate.google.com/translate?' . http_build_query(
                    array( 'sl' => 'it', 'tl' => $code, 'u' => $page_url ), '', '&', PHP_QUERY_RFC3986
                );
                ?>
                <li><a href="<?php echo esc_url( $translate_url ); ?>" lang="<?php echo esc_attr( $code ); ?>"
                       hreflang="<?php echo esc_attr( $code ); ?>"><?php echo esc_html( $language ); ?></a></li>
            <?php endforeach; ?>
        </ul>
        <small>Google Translate</small>
    </details>
    <?php
}

function aivision_reading_home() {
    echo '<div class="col-md-4 top-right-area">';
    aivision_reading_language();
    aivision_render_reading_widget();
    echo '</div>';
}

function aivision_reading_sidebar( $sidebar ) {
    if ( 'sidebar-1' === $sidebar ) {
        aivision_reading_language();
        aivision_render_reading_widget();
    }
}

function aivision_reading_styles() {
    wp_register_style( 'aivision-reading-widget', false, array( 'newsup-style' ) );
    wp_enqueue_style( 'aivision-reading-widget' );
    wp_add_inline_style( 'aivision-reading-widget', <<<'CSS'
.aiv-language {
    box-sizing: border-box;
    width: 100%;
    margin: 0 0 12px;
    border: 1px solid #cad8ec;
    border-radius: 11px;
    background: #f4f8ff;
    color: #203a60;
    font-size: .88rem;
}
.aiv-language summary {
    display: flex;
    align-items: center;
    gap: 9px;
    min-height: 42px;
    padding: 7px 11px;
    cursor: pointer;
    list-style: none;
    font-weight: 700;
}
.aiv-language summary::-webkit-details-marker { display: none; }
.aiv-language summary::after { content: '▾'; margin-inline-start: auto; }
.aiv-language[open] summary::after { transform: rotate(180deg); }
.aiv-language summary .fa-globe { font-size: 1.12rem; color: #305c9b; }
.aiv-language-alt { font-weight: 500; color: #51698a; }
.aiv-language ul {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: 4px;
    list-style: none;
    padding: 0 8px;
    margin: 0;
}
.aiv-language li { margin: 0; }
.aiv-language a { display: block; padding: 6px; color: #244f88; border-radius: 5px; }
.aiv-language a:hover { background: #deecff; text-decoration: underline; }
.aiv-language summary:focus-visible, .aiv-language a:focus-visible {
    outline: 2px solid #305c9b;
    outline-offset: -2px;
}
.aiv-language small { display: block; margin: 4px 13px 8px; color: #51698a; }
.aiv-reading {
    --reading-ink: #eff6ff;
    --reading-muted: #c5d6f1;
    --reading-accent: #8ce0ff;
    box-sizing: border-box;
    width: 100%;
    margin: 0 0 20px;
    padding: clamp(12px, 1.5vw, 20px);
    border: 1px solid #3a5785;
    border-radius: 16px;
    background: radial-gradient(ellipse at top right, #31598c, transparent 65%), #1b3356;
    color: var(--reading-ink);
    box-shadow: 0 8px 22px #101d3724;
}
.aiv-reading h2 {
    color: var(--reading-ink);
    font-size: clamp(1.15rem, 1.7vw, 1.55rem);
    line-height: 1.2;
    margin: 0 0 12px;
}
.aiv-reading-choice {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    opacity: 0;
    overflow: hidden;
    clip-path: inset(50%);
}
.aiv-reading-labels {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 4px;
    background: #172e50;
    border: 1px solid #46648e;
    border-radius: 10px;
}
.aiv-reading-labels label {
    flex: 1 1 auto;
    cursor: pointer;
    min-height: 36px;
    margin: 0;
    padding: 6px 7px;
    text-align: center;
    color: var(--reading-muted);
    font-size: .78rem;
    font-weight: 700;
    border-radius: 6px;
}
.aiv-reading-choice[data-view="trend"]:checked ~ .aiv-reading-labels [data-view="trend"],
.aiv-reading-choice[data-view="popular"]:checked ~ .aiv-reading-labels [data-view="popular"],
.aiv-reading-choice[data-view="latest"]:checked ~ .aiv-reading-labels [data-view="latest"] {
    color: #0c2240;
    background: var(--reading-accent);
}
.aiv-reading-choice[data-view="trend"]:focus-visible ~ .aiv-reading-labels [data-view="trend"],
.aiv-reading-choice[data-view="popular"]:focus-visible ~ .aiv-reading-labels [data-view="popular"],
.aiv-reading-choice[data-view="latest"]:focus-visible ~ .aiv-reading-labels [data-view="latest"] {
    outline: 2px solid #fff;
    outline-offset: 1px;
}
.aiv-reading-panel { display: none; }
.aiv-reading-choice[data-view="trend"]:checked ~ .aiv-reading-panel[data-view="trend"],
.aiv-reading-choice[data-view="popular"]:checked ~ .aiv-reading-panel[data-view="popular"],
.aiv-reading-choice[data-view="latest"]:checked ~ .aiv-reading-panel[data-view="latest"] { display: block; }
.aiv-reading .aiv-reading-period {
    margin: 10px 0 0;
    color: var(--reading-muted);
    font-size: .76rem;
}
.aiv-reading .aiv-reading-panel ul { list-style: none; margin: 5px 0 0; padding: 0; }
.aiv-reading .aiv-reading-panel li { border-bottom: 1px solid #49658d; margin: 0; padding: 0; }
.aiv-reading .aiv-reading-panel li:last-child { border-bottom: 0; }
.aiv-reading .aiv-reading-panel li a {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 0;
    color: var(--reading-ink);
    line-height: 1.35;
    font-size: .9rem;
    font-weight: 650;
}
.aiv-reading .aiv-reading-panel a:hover, .aiv-reading .aiv-reading-panel a:focus-visible {
    color: var(--reading-accent);
    text-decoration: underline;
}
.aiv-reading-thumb {
    flex: 0 0 clamp(52px, 5.8vw, 74px);
    aspect-ratio: 1.18;
    border-radius: 8px;
    overflow: hidden;
    background-color: #274875;
}
.aiv-reading-thumb img { display: block; width: 100%; height: 100%; object-fit: cover; }
.aiv-reading-title { min-width: 0; overflow-wrap: anywhere; }
CSS
    );
}

function aivision_mount_reading_widget() {
    if ( 'newsup' !== get_template() ) {
        return;
    }
    if ( is_front_page() && ! is_paged() ) {
        remove_action( 'newsup_action_banner_tabbed_posts', 'newsup_banner_tabbed_posts', 10 );
        add_action( 'newsup_action_banner_tabbed_posts', 'aivision_reading_home', 10 );
    } elseif ( is_singular( 'post' ) ) {
        add_action( 'dynamic_sidebar_before', 'aivision_reading_sidebar', 9 );
    } else {
        return;
    }
    add_action( 'wp_enqueue_scripts', 'aivision_reading_styles', 30 );
}
add_action( 'wp', 'aivision_mount_reading_widget', 20 );
