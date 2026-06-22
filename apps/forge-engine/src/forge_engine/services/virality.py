"""Virality scoring service with LLM-enhanced analysis."""

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from forge_engine.services.emotion_detection import (
        EmotionAnalysisResult,
        EmotionDetectionService,
    )
    from forge_engine.services.llm_local import LLMScoreResult, LocalLLMService

logger = logging.getLogger(__name__)


class ViralityScorer:
    """Service for scoring viral potential of video segments."""

    # Score weights (must sum to 100)
    WEIGHTS = {
        "hook_strength": 25,
        "payoff": 20,
        "humour_reaction": 15,
        "tension_surprise": 15,
        "clarity_autonomy": 15,
        "rhythm": 10,
    }

    # Hook detection patterns - enriched for FR streaming + Esport
    HOOK_PATTERNS = [
        # Questions
        (r"\?$", 3, "ends_with_question"),
        # French exclamations (classic)
        (r"\b(non mais|attends?|regarde[zs]?|wesh|wsh|putain|bordel|oh mon dieu|c'est pas possible)\b", 2, "french_exclamation"),
        # French streaming slang
        (r"\b(frère|frérot|gars|mec|wallah|sur ma vie|je te jure|jsuis|j'suis)\b", 2, "french_streaming"),
        # French reactions
        (r"\b(oh|waouh|naan|nan|ah ouais|c'est chaud|trop bien|genre|tranquille|oklm)\b", 2, "french_reaction"),
        # English exclamations
        (r"\b(wait|oh my god|holy|no way|what the|insane|crazy|bruh|bro)\b", 2, "english_exclamation"),
        # Direct address
        (r"\b(tu sais|vous savez|écoute|listen|check this|watch this|vas-?y|allez)\b", 2, "direct_address"),
        # Setup phrases
        (r"\b(alors|donc|en fait|basically|so basically|du coup|en mode)\b", 1, "setup_phrase"),
        # Intensifiers FR
        (r"\b(trop|vraiment|grave|carrément|clairement|littéralement)\b", 1, "intensifier"),
        # Esport hype phrases
        (r"\b(c'est fini|c'est gagné|c'est perdu|on a win|on a perdu|ça passe|ça passe pas)\b", 2, "esport_hype"),
        (r"\b(il est chaud|ils sont chauds|trop clutch|le outplay|la diff)\b", 2, "esport_hype"),
    ]

    # Content tags - enriched for FR streaming/gaming + Esport LoL + Karmine Corp
    CONTENT_PATTERNS = [
        # Humour
        (r"\b(mdr|lol|ptdr|haha|mort de rire|jpp|j'en peux plus|😂|🤣)\b", "humour"),
        (r"\b(trop fort|trop drôle|je suis mort|jsuis mort)\b", "humour"),
        # Surprise/Hype
        (r"\b(incroyable|dingue|ouf|insane|crazy|unbelievable|chaud|énorme)\b", "surprise"),
        (r"\b(what|quoi|sérieux|c'est quoi ça|wtf)\b", "surprise"),
        # Rage/Frustration
        (r"\b(rage|énervé|angry|pissed|furieux|ragequit|tilté|la haine)\b", "rage"),
        # Clutch/Victory
        (r"\b(clutch|win|gg|let's go|victory|on l'a|gagné|ez|easy)\b", "clutch"),
        # Debate/Discussion
        (r"\b(débat|argument|versus|vs|contre|par contre|mais non)\b", "debate"),
        # Fail/Death
        (r"\b(fail|rip|mort|dead|f in chat|miskine|aie|argh)\b", "fail"),
        # Gaming specific
        (r"\b(tryhard|nolife|no life|carried|boost|smurf|one shot|headshot)\b", "gaming"),
        # Streamer specific
        (r"\b(sub|abonne|follow|prime|donate|don|bits)\b", "streamer"),

        # ========== KARMINE CORP ==========
        # Team names & variations
        (r"\b(Karmine|Karmine Corp|KC|KCorp|K Corp|la Karmine|les bleus)\b", "karmine"),
        (r"\b(KCORP|#KCWIN|KC WIN|ALLEZ KC|KC GO|KCBLUE|KC BLUE)\b", "karmine"),
        # KC 2025-2026 Roster LoL
        (r"\b(Cabochard|Cabo|Gaboche)\b", "karmine_player"),  # Top
        (r"\b(Cinkrof|Cinkr)\b", "karmine_player"),  # Jungle
        (r"\b(Saken|Sak)\b", "karmine_player"),  # Mid
        (r"\b(Caliste|Cal)\b", "karmine_player"),  # ADC
        (r"\b(Targamas|Targa)\b", "karmine_player"),  # Support
        # KC Staff & Org
        (r"\b(Kameto|Kamel|Prime)\b", "karmine_org"),
        (r"\b(Kotei|Shaunz)\b", "karmine_staff"),
        # KC Historic players
        (r"\b(Rekkles|Rekk)\b", "karmine_player"),
        (r"\b(Upset|Hylissang|Hylli)\b", "karmine_player"),
        (r"\b(113|Hantera|Matty)\b", "karmine_player"),
        (r"\b(SLT|Scarlet|Adam)\b", "karmine_player"),

        # ========== LEAGUE OF LEGENDS TERMS ==========
        # Roles
        (r"\b(top lane|toplane|top|toplaner)\b", "lol_role"),
        (r"\b(jungle|jungler|jgl|jng)\b", "lol_role"),
        (r"\b(mid lane|midlane|mid|midlaner)\b", "lol_role"),
        (r"\b(adc|ad carry|bot lane|botlane|marksman)\b", "lol_role"),
        (r"\b(support|supp|sup)\b", "lol_role"),
        # Actions LoL
        (r"\b(gank|ganker|gankée?)\b", "lol_action"),
        (r"\b(dive|tower dive|plonge|plongée)\b", "lol_action"),
        (r"\b(roam|roaming|rotate|rotation)\b", "lol_action"),
        (r"\b(split|splitpush|split push)\b", "lol_action"),
        (r"\b(flash|ignite|tp|teleport|smite|exha|exhaust)\b", "lol_action"),
        (r"\b(poke|all-?in|trade|harass)\b", "lol_action"),
        (r"\b(kite|kiter|kiting)\b", "lol_action"),
        (r"\b(peel|peeler|engage|engager|disengage)\b", "lol_action"),
        # Objectives LoL
        (r"\b(drake|dragon|drag|infernal|mountain|ocean|cloud|hextech|chemtech|elder)\b", "lol_objective"),
        (r"\b(baron|nashor|nash|baron nashor)\b", "lol_objective"),
        (r"\b(herald|héraut|rift herald)\b", "lol_objective"),
        (r"\b(inhib|inhibiteur|inhibitor|nexus)\b", "lol_objective"),
        (r"\b(tower|tour|turret|tier 1|tier 2|tier 3|t1|t2|t3)\b", "lol_objective"),
        (r"\b(grubs|voidgrubs|void grubs)\b", "lol_objective"),
        # Game states
        (r"\b(early game|early|mid game|late game|late)\b", "lol_state"),
        (r"\b(teamfight|team fight|tf|fight|bagarre)\b", "lol_state"),
        (r"\b(ace|aced|pentakill|penta|quadra|triple kill|double kill)\b", "lol_state"),
        (r"\b(throw|thrower|comeback|reverse sweep)\b", "lol_state"),
        (r"\b(stomp|stomped|snowball|fed|feeder|feeding)\b", "lol_state"),
        (r"\b(outplay|outplayed|diff|gapped|gap)\b", "lol_state"),
        (r"\b(first blood|fb|first tower|first drake)\b", "lol_state"),
        # Items & economy
        (r"\b(item|stuff|gold|gold diff|cs|farm|wave|minion)\b", "lol_item"),
        (r"\b(mythique|légendaire|complet|full build|build)\b", "lol_item"),

        # ========== CHAMPIONS POPULAIRES ==========
        # Top lane
        (r"\b(Aatrox|Camille|Darius|Fiora|Gnar|Gragas|Gwen|Irelia|Jax|Jayce)\b", "lol_champ"),
        (r"\b(K'Santé|K'Sante|Ksante|Kennen|Malphite|Mordekaiser|Ornn|Renekton|Riven|Rumble)\b", "lol_champ"),
        (r"\b(Sett|Shen|Sion|Teemo|Tryndamere|Urgot|Volibear|Yasuo|Yone)\b", "lol_champ"),
        # Jungle
        (r"\b(Ambessa|Bel'?Veth|Briar|Diana|Elise|Evelynn|Graves|Hecarim|Ivern)\b", "lol_champ"),
        (r"\b(Jarvan|J4|Karthus|Kayn|Kha'?Zix|Kindred|Lee Sin|Lee|Lillia|Maokai)\b", "lol_champ"),
        (r"\b(Master Yi|Nidalee|Nocturne|Nunu|Olaf|Rek'?Sai|Rengar|Sejuani|Shaco)\b", "lol_champ"),
        (r"\b(Skarner|Sylas|Taliyah|Udyr|Viego|Vi|Warwick|Wukong|Xin Zhao|Zac)\b", "lol_champ"),
        # Mid lane
        (r"\b(Ahri|Akali|Akshan|Anivia|Annie|Aurelion Sol|Asol|Aurora|Azir|Cassiopeia)\b", "lol_champ"),
        (r"\b(Corki|Ekko|Fizz|Galio|Hwei|Kassadin|Katarina|Kata|LeBlanc|Lissandra)\b", "lol_champ"),
        (r"\b(Lux|Malzahar|Naafiri|Neeko|Orianna|Ori|Qiyana|Ryze|Smolder|Syndra)\b", "lol_champ"),
        (r"\b(Talon|Tristana|Twisted Fate|TF|Veigar|Vel'?Koz|Vex|Viktor|Vladimir|Vlad)\b", "lol_champ"),
        (r"\b(Xerath|Zed|Ziggs|Zoe)\b", "lol_champ"),
        # ADC
        (r"\b(Aphelios|Ashe|Caitlyn|Cait|Draven|Ezreal|Ez|Jhin|Jinx|Kai'?Sa|Kaisa)\b", "lol_champ"),
        (r"\b(Kalista|Kog'?Maw|Lucian|Miss Fortune|MF|Nilah|Samira|Senna|Sivir)\b", "lol_champ"),
        (r"\b(Twitch|Varus|Vayne|Xayah|Zeri)\b", "lol_champ"),
        # Support
        (r"\b(Alistar|Bard|Blitzcrank|Blitz|Braum|Janna|Karma|Leona|Lulu|Milio)\b", "lol_champ"),
        (r"\b(Morgana|Nami|Nautilus|Naut|Pyke|Rakan|Rell|Renata|Seraphine|Sona)\b", "lol_champ"),
        (r"\b(Soraka|Tahm Kench|TK|Taric|Thresh|Yuumi|Zilean|Zyra)\b", "lol_champ"),

        # ========== ESPORT LEC / LFL / INTERNATIONAL ==========
        # Ligues
        (r"\b(LEC|LFL|LCS|LCK|LPL|Worlds|MSI|All-?Star)\b", "esport_league"),
        (r"\b(playoffs|playoff|finale|demi-?finale|quart de finale|phase de groupe)\b", "esport_league"),
        # Équipes LEC 2026
        (r"\b(G2|G2 Esports|Fnatic|FNC|Fnatic|Team Vitality|Vitality|VIT)\b", "esport_team"),
        (r"\b(MAD Lions|MAD|Team BDS|BDS|SK Gaming|SK|Rogue|RGE)\b", "esport_team"),
        (r"\b(Excel|XL|Astralis|AST|Team Heretics|Heretics|TH)\b", "esport_team"),
        # Équipes LFL 2026
        (r"\b(LDLC|LDLC OL|Vitality\.Bee|VIT Bee|Solary|SLY|Gentle Mates|Gentlemates|GM)\b", "esport_team"),
        (r"\b(GameWard|GW|Aegis|Aegis Esport|BK ROG|BKROG|Mandatory|MDY)\b", "esport_team"),
        (r"\b(Team du Sud|TDS|Oplon|Zerance)\b", "esport_team"),
        # Joueurs LEC/LFL stars 2026
        (r"\b(Caps|Perkz|Jankos|Mikyx|BrokenBlade|BB|Odoamne|Wunder)\b", "esport_player"),
        (r"\b(Hans Sama|Hans|Vetheo|Elyoya|Razork|Humanoid|Larssen)\b", "esport_player"),
        (r"\b(Yike|Noah|Trymbi|Advienne|Crownie|Labrov|Jun|Nisqy)\b", "esport_player"),
        (r"\b(Canna|Zeus|Chovy|Showmaker|Faker|Gumayusi|Keria|Canyon|Oner)\b", "esport_player"),
        # Casters FR
        (r"\b(Chips|Noi|Chipsetnoi|Laure|Laure Valée|Valée|Rivenzi|Domingo)\b", "caster_fr"),
        (r"\b(Trasjk|Zaboutine|Zab|Tweekz|7ckingMad|Ceb)\b", "caster_fr"),

        # ========== EXPRESSIONS ESPORT ==========
        # Casting expressions
        (r"\b(c'est énorme|il le fait|il l'a fait|magnifique|sublime|incroyable)\b", "esport_cast"),
        (r"\b(et ça passe|ça ne passe pas|c'est fini|the nexus|the base)\b", "esport_cast"),
        (r"\b(baron steal|steal|volé|il le vole|dragon soul|soul|âme)\b", "esport_cast"),
        (r"\b(game point|match point|élimination|bracket|seeding)\b", "esport_cast"),
        # Community expressions
        (r"\b(banger|banger game|game of the year|goty|classique|classic)\b", "esport_community"),
        (r"\b(GOAT|goat|greatest|the best|le meilleur|meilleur joueur)\b", "esport_community"),
        (r"\b(MVP|mvp|player of the game|potg|player of the match)\b", "esport_community"),
        (r"\b(draft diff|draft kingdom|draft gap|pick ban|ban|pick)\b", "esport_community"),
        (r"\b(mental boom|mental|tilted|ego|ego diff|coaching diff)\b", "esport_community"),
        (r"\b(script|scripté|scripted|plot armor|remontada|comeback)\b", "esport_community"),
        (r"\b(blue side|red side|side selection|avantage)\b", "esport_community"),
    ]

    def __init__(self, use_llm: bool = True):
        # Clip duration range: 30s to 3min30
        self.min_duration = 30       # Minimum 30s
        self.max_duration = 210      # Max 3min30
        self.optimal_duration = 60   # Sweet spot for TikTok
        self.target_durations = [30, 45, 60, 75, 90, 120, 150, 180, 210]  # Sliding windows

        # LLM integration
        self.use_llm = use_llm
        self._llm_service: LocalLLMService | None = None
        self._llm_available: bool | None = None

        # Emotion detection integration
        self._emotion_service: EmotionDetectionService | None = None
        self._emotion_available: bool | None = None
        self._emotion_cache: dict[str, EmotionAnalysisResult] = {}

    async def _get_llm_service(self) -> Optional["LocalLLMService"]:
        """Get LLM service if available."""
        if not self.use_llm:
            return None

        if self._llm_service is None:
            try:
                from forge_engine.services.llm_local import LocalLLMService
                self._llm_service = LocalLLMService.get_instance()
                self._llm_available = await self._llm_service.check_availability()
            except Exception as e:
                logger.warning(f"LLM service not available: {e}")
                self._llm_available = False

        return self._llm_service if self._llm_available else None

    def _get_emotion_service(self) -> Optional["EmotionDetectionService"]:
        """Get emotion detection service if available."""
        if self._emotion_service is None:
            try:
                from forge_engine.services.emotion_detection import EmotionDetectionService
                self._emotion_service = EmotionDetectionService.get_instance()
                self._emotion_available = self._emotion_service.is_available()
            except Exception as e:
                logger.warning(f"Emotion detection service not available: {e}")
                self._emotion_available = False

        return self._emotion_service if self._emotion_available else None

    async def analyze_emotions_for_video(
        self,
        video_path: str,
        duration: float,
        cache_key: str | None = None
    ) -> Optional["EmotionAnalysisResult"]:
        """
        Analyze emotions for a video and cache the result.

        Args:
            video_path: Path to video file
            duration: Video duration
            cache_key: Optional cache key (e.g., project_id)

        Returns:
            EmotionAnalysisResult or None
        """
        # Check cache
        if cache_key and cache_key in self._emotion_cache:
            return self._emotion_cache[cache_key]

        service = self._get_emotion_service()
        if not service:
            return None

        try:
            result = await service.analyze_video(video_path, duration)
            if result and cache_key:
                self._emotion_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            return None

    def generate_segments(
        self,
        transcript_segments: list[dict[str, Any]],
        total_duration: float,
        audio_data: dict[str, Any] | None = None,
        scene_data: dict[str, Any] | None = None,
        window_sizes: list[int] = None
    ) -> list[dict[str, Any]]:
        """Generate candidate segments using sliding windows optimized for TikTok monetization."""
        if not transcript_segments:
            return []

        # Use target durations for TikTok monetization (60s minimum)
        if window_sizes is None:
            window_sizes = self.target_durations  # [60, 75, 90, 120, 150, 180]

        candidates = []
        scene_times = []

        # Get scene change times for natural break points
        if scene_data:
            scene_times = [s.get("time", 0) for s in scene_data.get("scenes", [])]

        for window_size in window_sizes:
            step = window_size // 3  # 33% overlap for better coverage

            current_time = 0
            while current_time + window_size <= total_duration:
                # Find transcript segments in this window
                window_transcripts = [
                    seg for seg in transcript_segments
                    if seg["start"] >= current_time and seg["end"] <= current_time + window_size
                ]

                if window_transcripts:
                    # Snap to sentence boundaries
                    start_time = window_transcripts[0]["start"]
                    end_time = window_transcripts[-1]["end"]

                    # Try to extend to natural break points (scene changes, pauses)
                    end_time = self._find_natural_end(
                        end_time,
                        transcript_segments,
                        scene_times,
                        self.min_duration,
                        self.max_duration
                    )

                    duration = end_time - start_time

                    # Ensure minimum duration for monetization
                    if duration >= self.min_duration:
                        # Get final transcript for the adjusted duration
                        final_transcripts = [
                            seg for seg in transcript_segments
                            if seg["start"] >= start_time and seg["end"] <= end_time
                        ]

                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": duration,
                            "transcript_segments": final_transcripts,
                            "transcript": " ".join(s["text"] for s in final_transcripts),
                            "window_size": window_size,
                        })

                current_time += step

        logger.info("Generated %d candidate segments (min %ds, target %ds)",
                    len(candidates), self.min_duration, self.optimal_duration)
        return candidates

    def _find_natural_end(
        self,
        current_end: float,
        transcript_segments: list[dict],
        scene_times: list[float],
        min_duration: float,
        max_duration: float
    ) -> float:
        """Find a natural ending point (pause, scene change, sentence end)."""
        # Look for scene changes near the current end
        for scene_time in scene_times:
            if current_end - 5 <= scene_time <= current_end + 10:
                return scene_time

        # Look for long pauses in transcript
        for i, seg in enumerate(transcript_segments):
            if seg["start"] > current_end + 10:
                break
            if seg["start"] > current_end - 5:
                # Check for pause before this segment
                if i > 0:
                    prev_end = transcript_segments[i-1]["end"]
                    gap = seg["start"] - prev_end
                    if gap > 1.0:  # 1+ second pause
                        return prev_end

        return current_end

    def score_segments(
        self,
        segments: list[dict[str, Any]],
        transcript_data: dict[str, Any] | None = None,
        audio_data: dict[str, Any] | None = None,
        scene_data: dict[str, Any] | None = None,
        chat_data: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Score all candidate segments (sync wrapper)."""
        scored = []

        for segment in segments:
            score = self._score_segment(segment, audio_data, scene_data, chat_data)
            segment["score"] = score
            segment["topic_label"] = self._generate_topic_label(segment)
            segment["hook_text"] = self._find_best_hook(segment)
            segment["cold_open_recommended"], segment["cold_open_start_time"] = \
                self._check_cold_open(segment)
            scored.append(segment)

        # Sort by total score
        scored.sort(key=lambda x: x["score"]["total"], reverse=True)

        return scored

    async def score_segments_async(
        self,
        segments: list[dict[str, Any]],
        transcript_data: dict[str, Any] | None = None,
        audio_data: dict[str, Any] | None = None,
        scene_data: dict[str, Any] | None = None,
        emotion_data: Optional["EmotionAnalysisResult"] = None,
        use_llm: bool = True,
        use_emotions: bool = True,
        chat_data: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Score all candidate segments with optional LLM and emotion enhancement."""
        # First, apply heuristic scoring
        scored = self.score_segments(segments, transcript_data, audio_data, scene_data, chat_data)

        # Enhance with emotion data if available
        if use_emotions and emotion_data:
            logger.info("Enhancing segments with emotion analysis...")
            emotion_service = self._get_emotion_service()
            if emotion_service:
                for segment in scored:
                    emotion_scores = emotion_service.get_emotion_score_for_segment(
                        emotion_data,
                        segment.get("start_time", 0),
                        segment.get("end_time", 0)
                    )
                    self._merge_emotion_scores(segment, emotion_scores)

        # If LLM is enabled, enhance top segments with LLM analysis
        if use_llm and self.use_llm:
            llm = await self._get_llm_service()
            if llm:
                # Only score top 50 segments with LLM to save time
                top_segments = scored[:50]
                logger.info(f"Enhancing {len(top_segments)} segments with LLM scoring...")

                llm_results = await llm.batch_score_segments(
                    [{"transcript": s.get("transcript", ""), "duration": s.get("duration", 60)}
                     for s in top_segments],
                    max_concurrent=3
                )

                # Merge LLM scores with heuristic scores
                for _i, (segment, llm_result) in enumerate(zip(top_segments, llm_results, strict=False)):
                    if llm_result:
                        self._merge_llm_scores(segment, llm_result)

                # Re-sort after LLM enhancement
                scored.sort(key=lambda x: x["score"]["total"], reverse=True)
                logger.info("LLM scoring complete")

        return scored

    def _merge_emotion_scores(
        self,
        segment: dict[str, Any],
        emotion_scores: dict[str, Any]
    ) -> None:
        """Merge emotion detection scores into segment score."""
        score = segment.get("score", {})

        emotion_score = emotion_scores.get("emotion_score", 0)
        emotion_tags = emotion_scores.get("emotion_tags", [])
        peak_emotion = emotion_scores.get("peak_emotion")

        # Add emotion contribution to tension/surprise score
        # Blend: 70% original, 30% emotion
        original_tension = score.get("tension_surprise", 0)
        score["tension_surprise"] = (original_tension * 0.7) + (emotion_score * 0.3)
        score["tension_surprise"] = min(score["tension_surprise"], 15)

        # Recalculate total
        score["total"] = min(100, (
            score.get("hook_strength", 0) +
            score.get("payoff", 0) +
            score.get("humour_reaction", 0) +
            score.get("tension_surprise", 0) +
            score.get("clarity_autonomy", 0) +
            score.get("rhythm", 0)
        ))

        # Add emotion metadata
        score["emotion_enhanced"] = True
        score["peak_emotion"] = peak_emotion

        # Merge tags
        existing_tags = set(score.get("tags", []))
        existing_tags.update(emotion_tags)
        score["tags"] = list(existing_tags)[:10]

        # Add reason if significant emotion detected
        if peak_emotion and peak_emotion != "neutral":
            reason = f"Peak emotion: {peak_emotion}"
            if reason not in score.get("reasons", []):
                score["reasons"] = score.get("reasons", [])[:4] + [reason]

        segment["score"] = score

    def _merge_llm_scores(
        self,
        segment: dict[str, Any],
        llm_result: "LLMScoreResult"
    ) -> None:
        """Merge LLM scores with heuristic scores."""
        score = segment.get("score", {})

        # Calculate LLM contribution (weighted average)
        # LLM scores are 0-10, scale to match our weights
        llm_humor = (llm_result.humor_score / 10) * 15  # Max 15 for humour
        llm_surprise = (llm_result.surprise_score / 10) * 15  # Max 15 for tension
        llm_hook = (llm_result.hook_score / 10) * 25  # Max 25 for hook
        llm_clarity = (llm_result.clarity_score / 10) * 15  # Max 15 for clarity

        # Blend heuristic and LLM scores (60% heuristic, 40% LLM)
        blend_ratio = 0.4

        score["humour_reaction"] = (
            score.get("humour_reaction", 0) * (1 - blend_ratio) +
            llm_humor * blend_ratio
        )
        score["tension_surprise"] = (
            score.get("tension_surprise", 0) * (1 - blend_ratio) +
            llm_surprise * blend_ratio
        )
        score["hook_strength"] = (
            score.get("hook_strength", 0) * (1 - blend_ratio) +
            llm_hook * blend_ratio
        )
        score["clarity_autonomy"] = (
            score.get("clarity_autonomy", 0) * (1 - blend_ratio) +
            llm_clarity * blend_ratio
        )

        # Recalculate total
        score["total"] = min(100, (
            score.get("hook_strength", 0) +
            score.get("payoff", 0) +
            score.get("humour_reaction", 0) +
            score.get("tension_surprise", 0) +
            score.get("clarity_autonomy", 0) +
            score.get("rhythm", 0)
        ))

        # Add LLM metadata
        score["llm_enhanced"] = True
        score["llm_reasoning"] = llm_result.reasoning
        score["llm_engagement"] = llm_result.engagement_score

        # Merge LLM tags with existing tags
        existing_tags = set(score.get("tags", []))
        llm_tags = set(llm_result.tags)
        score["tags"] = list(existing_tags | llm_tags)[:10]

        # Add reasoning to existing reasons
        if llm_result.reasoning and llm_result.reasoning not in score.get("reasons", []):
            score["reasons"] = score.get("reasons", [])[:4] + [f"LLM: {llm_result.reasoning}"]

        segment["score"] = score

    def _score_segment(
        self,
        segment: dict[str, Any],
        audio_data: dict[str, Any] | None = None,
        scene_data: dict[str, Any] | None = None,
        chat_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Calculate viral score for a segment."""
        transcript = segment.get("transcript", "").lower()
        transcript_segs = segment.get("transcript_segments", [])

        reasons = []
        tags = set()

        # Hook strength (0-25)
        hook_score = 0
        for pattern, points, reason in self.HOOK_PATTERNS:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches:
                hook_score += points * min(len(matches), 3)
                reasons.append(f"Hook: {reason}")

        # Check for strong opening
        if transcript_segs:
            first_seg = transcript_segs[0]
            if first_seg.get("is_potential_hook"):
                hook_score += 5
                reasons.append("Strong opening hook")

        hook_score = min(hook_score, 25)

        # Payoff (0-20)
        payoff_score = 0

        # Check for conclusion markers
        conclusion_patterns = [
            r"\b(voilà|done|that's it|boom|let's go|gg)\b",
            r"!{2,}",  # Multiple exclamation marks
        ]
        for pattern in conclusion_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                payoff_score += 5
                reasons.append("Strong conclusion")

        # Duration bonus for optimal TikTok length (45-90s is sweet spot)
        duration = segment.get("duration", 60)
        if 45 <= duration <= 90:
            payoff_score += 5
            reasons.append("Optimal duration (45-90s)")
        elif 60 <= duration <= 120:
            payoff_score += 3
            reasons.append("Good duration (60-120s)")

        # Last segment energy
        if transcript_segs and len(transcript_segs) > 1:
            last_seg = transcript_segs[-1]
            if last_seg.get("hook_score", 0) >= 2:
                payoff_score += 5
                reasons.append("Strong ending")

        payoff_score = min(payoff_score, 20)

        # Humour/Reaction (0-15)
        humour_score = 0

        for pattern, tag in self.CONTENT_PATTERNS:
            if re.search(pattern, transcript, re.IGNORECASE):
                if tag == "humour":
                    humour_score += 5
                    tags.add(tag)
                    reasons.append("Contains humor markers")
                elif tag in ("surprise", "rage", "fail"):
                    humour_score += 3
                    tags.add(tag)

        humour_score = min(humour_score, 15)

        # Tension/Surprise (0-15)
        tension_score = 0

        # Tracks whether this window has any acoustic excitement, for the
        # chat+audio dual-gate combo below.
        audio_hot = False

        # Audio energy variance (if available)
        if audio_data:
            energy = audio_data.get("energy_timeline", [])
            segment_energy = [
                e for e in energy
                if segment["start_time"] <= e.get("time", 0) <= segment["end_time"]
            ]
            if segment_energy:
                values = [e.get("value", 0) for e in segment_energy]
                if values:
                    variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
                    if variance > 0.1:
                        tension_score += 5
                        audio_hot = True
                        reasons.append("High audio variance")

            # Detected audio EVENTS (laughter/cheer/scream/...): the highest-signal
            # "something funny/hype happened here" cues, previously computed then
            # discarded. Laughter/cheer/applause lift humour; scream/gasp/excitement/
            # game beats lift tension. Weighted by the detector's confidence-scaled
            # viral_score (0-1). Humour is re-capped since it was clamped above.
            HUMOUR_EVENTS = {"laughter", "cheer", "applause"}
            TENSION_EVENTS = {
                "scream", "gasp", "speech_excitement",
                "game_explosion", "game_achievement", "game_gunshot",
            }
            seg_events = [
                ev for ev in audio_data.get("events", [])
                if segment["start_time"] <= ev.get("start", ev.get("time", 0)) <= segment["end_time"]
            ]
            humour_hits = [e for e in seg_events if e.get("type") in HUMOUR_EVENTS]
            tension_hits = [e for e in seg_events if e.get("type") in TENSION_EVENTS]
            if seg_events:
                audio_hot = True
            if humour_hits:
                strength = max(e.get("viral_score") or e.get("confidence", 0.0) for e in humour_hits)
                humour_score = min(humour_score + round(8 * strength), 15)
                tags.add("audio_reaction")
                kinds = ", ".join(sorted({e["type"] for e in humour_hits}))
                reasons.append(f"Audio reaction ({kinds})")
            if tension_hits:
                strength = max(e.get("viral_score") or e.get("confidence", 0.0) for e in tension_hits)
                tension_score += round(6 * strength)
                kinds = ", ".join(sorted({e["type"] for e in tension_hits}))
                reasons.append(f"Audio spike ({kinds})")

        # Twitch chat spikes — the strongest real-world "clip it" signal. A spike
        # inside the window lifts tension (hype) / humour (laugh); when it
        # COINCIDES with acoustic excitement ("chat spikes AND voice loud"), add a
        # combo bonus — the canonical stream funny-moment marker.
        if chat_data:
            seg_spikes = [
                s for s in chat_data.get("spikes", [])
                if segment["start_time"] <= s.get("time", -1) <= segment["end_time"]
            ]
            if seg_spikes:
                peak = max(s.get("intensity", 0.0) for s in seg_spikes)
                chat_boost = min(7, round(1.5 * peak))  # z=2 -> ~3, z>=5 -> cap 7
                if any(s.get("kind") == "laugh" for s in seg_spikes):
                    humour_score = min(humour_score + chat_boost, 15)
                    tags.add("chat_laugh")
                tension_score += chat_boost
                tags.add("chat_spike")
                reasons.append(f"Chat spike (x{len(seg_spikes)}, z={peak:.1f})")
                if audio_hot:
                    tension_score += 3
                    reasons.append("Chat + audio peak (combo)")

        # Scene changes
        if scene_data:
            scenes = scene_data.get("scenes", [])
            segment_scenes = [
                s for s in scenes
                if segment["start_time"] <= s.get("time", 0) <= segment["end_time"]
            ]
            if len(segment_scenes) >= 2:
                tension_score += 5
                reasons.append("Multiple scene changes")

        # Content tension markers
        tension_patterns = [
            r"\b(suspense|tension|stress|anxieux|nervous)\b",
            r"\b(mais|but|however|pourtant)\b",  # Contrast markers
        ]
        for pattern in tension_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                tension_score += 3

        tension_score = min(tension_score, 15)

        # Clarity/Autonomy (0-15)
        clarity_score = 10  # Base score

        # Penalize if context seems needed
        context_markers = [
            r"^(donc|alors|et|and|so)\b",  # Starts with connector
            r"\b(comme je disais|as I said|earlier)\b",  # References previous
        ]
        for pattern in context_markers:
            if re.search(pattern, transcript, re.IGNORECASE):
                clarity_score -= 3
                reasons.append("May need context")

        # Bonus for self-contained phrases
        if len(transcript_segs) >= 3:
            clarity_score += 3
            reasons.append("Self-contained narrative")

        clarity_score = max(0, min(clarity_score, 15))

        # Rhythm (0-10)
        rhythm_score = 5  # Base score

        # Check speech pacing
        word_count = len(transcript.split())
        words_per_second = word_count / max(duration, 1)

        if 2.0 <= words_per_second <= 3.5:  # Good pacing
            rhythm_score += 3
            reasons.append("Good speech pacing")

        # Short punchy sentences
        sentences = re.split(r'[.!?]', transcript)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        if 5 <= avg_sentence_length <= 12:
            rhythm_score += 2
            reasons.append("Punchy sentences")

        rhythm_score = min(rhythm_score, 10)

        # Calculate total
        total = hook_score + payoff_score + humour_score + tension_score + clarity_score + rhythm_score

        # Detect content tags
        for pattern, tag in self.CONTENT_PATTERNS:
            if re.search(pattern, transcript, re.IGNORECASE):
                tags.add(tag)

        result = {
            "total": min(total, 100),
            "hook_strength": hook_score,
            "payoff": payoff_score,
            "humour_reaction": humour_score,
            "tension_surprise": tension_score,
            "clarity_autonomy": clarity_score,
            "rhythm": rhythm_score,
            "reasons": reasons[:5],  # Limit to top 5 reasons
            "tags": list(tags),
        }

        # Apply v2 quality boosters (recalibrated duration, filler penalty,
        # lead-silence detection, combo bonus). Toggle with FORGE_VIRALITY_QUALITY_V2.
        from forge_engine.services.virality_quality import apply_quality_boosters

        return apply_quality_boosters(result, segment)

    def _generate_topic_label(self, segment: dict[str, Any]) -> str:
        """Generate a short topic label for the segment."""
        transcript = segment.get("transcript", "")

        # Use first sentence or phrase
        sentences = re.split(r'[.!?]', transcript)
        if sentences:
            first = sentences[0].strip()
            if len(first) > 40:
                first = first[:37] + "..."
            return first

        return "Segment"

    def _find_best_hook(self, segment: dict[str, Any]) -> str | None:
        """Find the best hook text in the segment."""
        transcript_segs = segment.get("transcript_segments", [])

        if not transcript_segs:
            return None

        # Find segment with highest hook score
        best_hook = max(transcript_segs, key=lambda x: x.get("hook_score", 0))

        if best_hook.get("hook_score", 0) >= 2:
            return best_hook.get("text", "")

        return transcript_segs[0].get("text", "")

    def _check_cold_open(self, segment: dict[str, Any]) -> tuple[bool, float | None]:
        """Check if cold open would work for this segment."""
        transcript_segs = segment.get("transcript_segments", [])

        if not transcript_segs or len(transcript_segs) < 3:
            return False, None

        # Find best hook that's not at the start
        best_idx = 0
        best_score = 0

        for i, seg in enumerate(transcript_segs[1:], 1):  # Skip first
            score = seg.get("hook_score", 0)
            if score > best_score:
                best_score = score
                best_idx = i

        # Only recommend if we found a strong hook not at start
        if best_score >= 3 and best_idx > 0:
            return True, transcript_segs[best_idx]["start"]

        return False, None

    def deduplicate_segments(
        self,
        segments: list[dict[str, Any]],
        iou_threshold: float = 0.5,
        max_segments: int = 500
    ) -> list[dict[str, Any]]:
        """Remove overlapping segments, keeping higher scored ones."""
        if not segments:
            return []

        # Sort by score descending
        sorted_segs = sorted(segments, key=lambda x: x["score"]["total"], reverse=True)

        kept = []

        for seg in sorted_segs:
            if len(kept) >= max_segments:
                break

            # Check overlap with kept segments
            dominated = False
            for kept_seg in kept:
                iou = self._calculate_iou(seg, kept_seg)
                if iou > iou_threshold:
                    dominated = True
                    break

            if not dominated:
                kept.append(seg)

        return kept

    def _calculate_iou(self, seg1: dict, seg2: dict) -> float:
        """Calculate intersection over union of two segments."""
        start1, end1 = seg1["start_time"], seg1["end_time"]
        start2, end2 = seg2["start_time"], seg2["end_time"]

        intersection_start = max(start1, start2)
        intersection_end = min(end1, end2)

        if intersection_start >= intersection_end:
            return 0.0

        intersection = intersection_end - intersection_start
        union = (end1 - start1) + (end2 - start2) - intersection

        return intersection / union if union > 0 else 0.0

    def generate_hook_timeline(
        self,
        transcript_segments: list[dict[str, Any]],
        total_duration: float,
        resolution: float = 1.0
    ) -> list[dict[str, Any]]:
        """Generate hook likelihood timeline data."""
        timeline = []

        current_time = 0
        while current_time < total_duration:
            # Find segments near this time
            nearby_score = 0
            for seg in transcript_segments:
                if abs(seg["start"] - current_time) < 5:  # Within 5 seconds
                    nearby_score += seg.get("hook_score", 0)

            timeline.append({
                "time": current_time,
                "value": min(nearby_score / 10, 1.0),  # Normalize to 0-1
            })

            current_time += resolution

        return timeline


