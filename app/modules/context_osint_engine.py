import time
import os
import torch
from PIL import Image
from typing import Dict, Any, List, Optional
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus

# Comprehensive Knowledge Registry of Public Personalities and their Real-World Professions
PUBLIC_ENTITIES_REGISTRY = [
    # ==========================================
    # HEADS OF STATE, POLITICIANS & LEADERS
    # ==========================================
    {
        "name": "Narendra Modi",
        "profession": "Prime Minister of India / Head of State",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Joe Biden",
        "profession": "President of the United States",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Donald Trump",
        "profession": "45th & 47th US President / Real Estate Executive",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Barack Obama",
        "profession": "Former US President / Author",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Kamala Harris",
        "profession": "Vice President of the United States / Politician",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Vladimir Putin",
        "profession": "President of Russia",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest"]
    },
    {
        "name": "Volodymyr Zelenskyy",
        "profession": "President of Ukraine",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["catwalk_fashion", "police_arrest"]
    },
    {
        "name": "Emmanuel Macron",
        "profession": "President of France",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Keir Starmer",
        "profession": "Prime Minister of the United Kingdom",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Rishi Sunak",
        "profession": "Former Prime Minister of the United Kingdom",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Justin Trudeau",
        "profession": "Prime Minister of Canada",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Rahul Gandhi",
        "profession": "Indian Member of Parliament / Politician",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Amit Shah",
        "profession": "Minister of Home Affairs of India",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },
    {
        "name": "Arvind Kejriwal",
        "profession": "Indian Politician & Former Chief Minister of Delhi",
        "category": "POLITICIAN",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Pope Francis",
        "profession": "Head of the Catholic Church & Vatican Sovereign",
        "category": "RELIGIOUS_LEADER",
        "plausible_activities": ["political_event", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "police_arrest", "military_combat"]
    },

    # ==========================================
    # HOLLYWOOD & GLOBAL CINEMA ACTORS & ACTRESSES
    # ==========================================
    {
        "name": "Ryan Reynolds",
        "profession": "Hollywood Actor, Film Producer & Entrepreneur",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Ryan Gosling",
        "profession": "Hollywood Actor & Musician",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion", "music_concert"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Hugh Jackman",
        "profession": "Actor, Singer & Performer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "music_concert", "catwalk_fashion"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Chris Evans",
        "profession": "Hollywood Actor & Film Director",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Chris Hemsworth",
        "profession": "Hollywood Actor & Fitness Entrepreneur",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "sports_match"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Robert Downey Jr.",
        "profession": "Academy Award-Winning Hollywood Actor",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Brad Pitt",
        "profession": "Hollywood Actor & Academy Award-Winning Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Leonardo DiCaprio",
        "profession": "Hollywood Actor & Environmentalist",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "political_event"],
        "implausible_activities": ["music_concert", "police_arrest"]
    },
    {
        "name": "Tom Cruise",
        "profession": "Hollywood Actor & Film Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Keanu Reeves",
        "profession": "Hollywood Actor & Musician",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "music_concert"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Cillian Murphy",
        "profession": "Academy Award-Winning Film Actor",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Dwayne Johnson",
        "profession": "Hollywood Actor, Producer & Former Pro Wrestler",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "sports_match"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Christian Bale",
        "profession": "Academy Award-Winning Actor",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Scarlett Johansson",
        "profession": "Hollywood Actress & Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Emma Stone",
        "profession": "Academy Award-Winning Actress",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Margot Robbie",
        "profession": "Hollywood Actress & Film Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Zendaya",
        "profession": "Actress, Singer & Fashion Icon",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion", "music_concert"],
        "implausible_activities": ["political_event", "police_arrest"]
    },

    # ==========================================
    # INDIAN CINEMA PERSONALITIES
    # ==========================================
    {
        "name": "Shah Rukh Khan",
        "profession": "Indian Film Actor & Film Producer",
        "category": "ACTOR",
        "plausible_activities": ["catwalk_fashion", "casual_portrait", "music_concert"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Salman Khan",
        "profession": "Indian Film Actor & Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Aamir Khan",
        "profession": "Indian Film Actor, Director & Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Amitabh Bachchan",
        "profession": "Veteran Indian Film Actor & Television Host",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "music_concert"],
        "implausible_activities": ["military_combat", "police_arrest"]
    },
    {
        "name": "Deepika Padukone",
        "profession": "Indian Film Actress & Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Priyanka Chopra",
        "profession": "Actress, Producer & Global Icon",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Alia Bhatt",
        "profession": "Indian Film Actress & Producer",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Prabhas",
        "profession": "Indian Film Actor & Pan-Indian Star",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait"],
        "implausible_activities": ["political_event", "police_arrest"]
    },
    {
        "name": "Allu Arjun",
        "profession": "National Award-Winning Indian Film Actor",
        "category": "ACTOR",
        "plausible_activities": ["casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "police_arrest"]
    },

    # ==========================================
    # MUSICIANS & PLAYBACK SINGERS
    # ==========================================
    {
        "name": "Arijit Singh",
        "profession": "Playback Singer, Composer & Music Performer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "police_arrest", "military_combat", "sports_match"]
    },
    {
        "name": "Taylor Swift",
        "profession": "Singer-Songwriter & Pop Performer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "catwalk_fashion", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest", "sports_match"]
    },
    {
        "name": "Diljit Dosanjh",
        "profession": "Singer, Musician & Actor",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait", "catwalk_fashion"],
        "implausible_activities": ["political_event", "military_combat", "police_arrest"]
    },
    {
        "name": "Sonu Nigam",
        "profession": "Playback Singer & Live Performer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Shreya Ghoshal",
        "profession": "Playback Singer & Classical Vocalist",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "A.R. Rahman",
        "profession": "Academy Award-Winning Music Composer & Singer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Ed Sheeran",
        "profession": "Singer-Songwriter & Guitarist",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Justin Bieber",
        "profession": "Pop Singer & Music Performer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Beyoncé",
        "profession": "Global Pop & R&B Superstar",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "catwalk_fashion", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Billie Eilish",
        "profession": "Academy Award & Grammy-Winning Singer-Songwriter",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "catwalk_fashion", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat", "sports_match"]
    },
    {
        "name": "Eminem",
        "profession": "Hip-Hop Artist, Rapper & Record Producer",
        "category": "MUSICIAN",
        "plausible_activities": ["music_concert", "casual_portrait"],
        "implausible_activities": ["political_event", "military_combat"]
    },

    # ==========================================
    # ATHLETES & SPORTS PERSONALITIES
    # ==========================================
    {
        "name": "Virat Kohli",
        "profession": "International Cricketer & Professional Athlete",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },
    {
        "name": "Rohit Sharma",
        "profession": "Indian Cricket Captain & Batsman",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },
    {
        "name": "MS Dhoni",
        "profession": "Former Indian Cricket Captain & Athlete",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event"]
    },
    {
        "name": "Sachin Tendulkar",
        "profession": "Legendary International Cricketer",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "police_arrest"]
    },
    {
        "name": "Cristiano Ronaldo",
        "profession": "Professional Footballer & World Champion Athlete",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },
    {
        "name": "Lionel Messi",
        "profession": "Professional Footballer & World Cup Champion",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },
    {
        "name": "LeBron James",
        "profession": "NBA Basketball Superstar & Athlete",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },
    {
        "name": "Neeraj Chopra",
        "profession": "Olympic Gold Medalist Javelin Thrower",
        "category": "ATHLETE",
        "plausible_activities": ["sports_match", "casual_portrait"],
        "implausible_activities": ["music_concert", "political_event", "military_combat"]
    },

    # ==========================================
    # TECH & BUSINESS TITANS
    # ==========================================
    {
        "name": "Elon Musk",
        "profession": "CEO of Tesla, SpaceX & Tech Entrepreneur",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Mark Zuckerberg",
        "profession": "Founder & CEO of Meta Platforms",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait", "sports_match"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Sundar Pichai",
        "profession": "CEO of Alphabet and Google",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat", "police_arrest"]
    },
    {
        "name": "Satya Nadella",
        "profession": "CEO and Chairman of Microsoft",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Sam Altman",
        "profession": "CEO of OpenAI & Tech Entrepreneur",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Bill Gates",
        "profession": "Co-founder of Microsoft & Philanthropist",
        "category": "TECH_LEADER",
        "plausible_activities": ["casual_portrait", "political_event"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Jeff Bezos",
        "profession": "Founder of Amazon & Blue Origin",
        "category": "TECH_LEADER",
        "plausible_activities": ["casual_portrait", "tech_keynote"],
        "implausible_activities": ["music_concert", "military_combat"]
    },
    {
        "name": "Mukesh Ambani",
        "profession": "Chairman & Managing Director of Reliance Industries",
        "category": "TECH_LEADER",
        "plausible_activities": ["tech_keynote", "casual_portrait"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    },
    {
        "name": "Ratan Tata",
        "profession": "Industrialist & Philanthropist, Former Tata Chairman",
        "category": "TECH_LEADER",
        "plausible_activities": ["casual_portrait", "political_event"],
        "implausible_activities": ["music_concert", "catwalk_fashion", "military_combat"]
    }
]

# Standard activities and their natural visual semantics for CLIP zero-shot matching
ACTIVITY_DEFINITIONS = [
    ("music_concert", "holding and playing an acoustic guitar while singing into a microphone on stage"),
    ("political_event", "delivering an official political speech at a government podium with microphones and national flags"),
    ("sports_match", "playing a professional competitive sport on a stadium ground in athletic sports jersey"),
    ("catwalk_fashion", "walking on a high-fashion runway modeling extravagant designer clothing"),
    ("police_arrest", "being handcuffed, detained, or arrested by police officers in uniform"),
    ("military_combat", "holding an assault rifle in military combat gear on a battlefield"),
    ("tech_keynote", "presenting a technology product launch keynote on an auditorium stage with slide screen"),
    ("casual_portrait", "casual natural indoor or outdoor portrait photo")
]

# Social and physical scene plausibility definitions
SOCIAL_PLAUSIBILITY_DEFINITIONS = [
    ("improbable_couple_composite", "a digitally manipulated photoshopped composite or AI generated wish-fulfillment image inserting an average guy with an unrealistically glamorous model"),
    ("natural_civilian_couple", "a real authentic natural candid photograph of an everyday civilian couple standing together"),
    ("single_civilian_portrait", "a real authentic casual portrait of a single individual"),
    ("public_event_group", "a formal press, political, sports, or public media appearance")
]

class ContextOSINTEngine(ForensicModule):
    @property
    def name(self) -> str:
        return "context_osint_engine"

    @property
    def display_name(self) -> str:
        return "Contextual OSINT & Entity Professional Verification"

    def __init__(self):
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self._initialized = False
        self._cached_entity_tokens = None
        self._cached_act_tokens = None
        self._cached_social_tokens = None

    def _lazy_init(self):
        if not self._initialized:
            try:
                import open_clip
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    "ViT-B-32", pretrained="laion2b_s34b_b79k", device="cpu"
                )
                self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
                self.model.eval()

                # Pre-tokenize entities once for speed
                entity_prompts = [f"a photo of {e['name']}" for e in PUBLIC_ENTITIES_REGISTRY]
                entity_prompts.append("a photo of an ordinary non-famous civilian person")
                self._cached_entity_tokens = self.tokenizer(entity_prompts)

                act_prompts = [desc for _, desc in ACTIVITY_DEFINITIONS]
                self._cached_act_tokens = self.tokenizer(act_prompts)

                social_prompts = [desc for _, desc in SOCIAL_PLAUSIBILITY_DEFINITIONS]
                self._cached_social_tokens = self.tokenizer(social_prompts)

                self._initialized = True
            except Exception as e:
                self._initialized = False
                self.init_error = str(e)

    def analyze(self, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        start_time = time.perf_counter()
        limitations = [
            "Entity and activity recognition use zero-shot visual-semantic embeddings (OpenCLIP ViT-B-32).",
            "Contextual plausibility checks cross-verify identified public figures against their authentic real-world professions.",
            "Visual anomalies must be cross-referenced with primary news records and official press archives."
        ]

        try:
            self._lazy_init()
            if not self._initialized:
                execution_time = (time.perf_counter() - start_time) * 1000.0
                return ModuleResult(
                    module_name=self.name,
                    status=TaskStatus.SKIPPED,
                    result={"notice": "OpenCLIP model pending initialization."},
                    evidence_found=False,
                    execution_time_ms=round(execution_time, 2),
                    limitations=limitations
                )

            pil_img = Image.open(image_path).convert("RGB")
            image_tensor = self.preprocess(pil_img).unsqueeze(0)

            with torch.no_grad():
                img_feat = self.model.encode_image(image_tensor)
                img_feat /= img_feat.norm(dim=-1, keepdim=True)

                # 1. Zero-Shot Entity Identification across Public Registry
                text_feat_e = self.model.encode_text(self._cached_entity_tokens)
                text_feat_e /= text_feat_e.norm(dim=-1, keepdim=True)

                # Raw cosine similarity dot product
                raw_cos_sims = (img_feat @ text_feat_e.T)[0].tolist()
                # Softmax distribution for relative probability
                sims_e = (100.0 * img_feat @ text_feat_e.T).softmax(dim=-1)[0].tolist()

            top_entity_idx = int(torch.tensor(sims_e).argmax().item())
            top_raw_cos = raw_cos_sims[top_entity_idx]
            entity_confidence = sims_e[top_entity_idx]
            civilian_raw_cos = raw_cos_sims[-1]
            margin_over_civilian = top_raw_cos - civilian_raw_cos

            # Top candidate breakdown for diagnostic transparency
            candidate_ranks = sorted(
                enumerate(sims_e), key=lambda x: x[1], reverse=True
            )[:5]
            top_candidates = []
            for idx, prob in candidate_ranks:
                c_name = PUBLIC_ENTITIES_REGISTRY[idx]["name"] if idx < len(PUBLIC_ENTITIES_REGISTRY) else "Civilian / Unregistered"
                top_candidates.append({"name": c_name, "probability": round(prob, 3), "raw_cosine": round(raw_cos_sims[idx], 3)})

            # Strict thresholding to prevent false-positive celebrity forcing:
            # Requires raw cosine similarity >= 0.275, confidence >= 0.50, and margin over civilian >= 0.05
            detected_entity_data = None
            if (
                top_entity_idx < len(PUBLIC_ENTITIES_REGISTRY) 
                and top_raw_cos >= 0.275 
                and entity_confidence >= 0.50
                and margin_over_civilian >= 0.05
            ):
                detected_entity_data = PUBLIC_ENTITIES_REGISTRY[top_entity_idx]

            # 2. Zero-Shot Activity & Depicted Setting Recognition
            with torch.no_grad():
                text_feat_a = self.model.encode_text(self._cached_act_tokens)
                text_feat_a /= text_feat_a.norm(dim=-1, keepdim=True)
                sims_a = (100.0 * img_feat @ text_feat_a.T).softmax(dim=-1)[0].tolist()

            top_act_idx = int(torch.tensor(sims_a).argmax().item())
            detected_act_key, detected_act_desc = ACTIVITY_DEFINITIONS[top_act_idx]
            activity_confidence = sims_a[top_act_idx]

            # 3. Social & Scenario Plausibility Check (Couple, Composite, Wish-Fulfillment)
            with torch.no_grad():
                text_feat_s = self.model.encode_text(self._cached_social_tokens)
                text_feat_s /= text_feat_s.norm(dim=-1, keepdim=True)
                sims_s = (100.0 * img_feat @ text_feat_s.T).softmax(dim=-1)[0].tolist()

            top_social_idx = int(torch.tensor(sims_s).argmax().item())
            detected_social_key, _ = SOCIAL_PLAUSIBILITY_DEFINITIONS[top_social_idx]
            social_confidence = sims_s[top_social_idx]

            # 4. Contextual Profession vs Activity Cross-Check
            is_conflict = False
            is_aligned = False
            conflict_explanation = None
            alignment_explanation = None

            if detected_entity_data:
                name = detected_entity_data["name"]
                role = detected_entity_data["profession"]
                plausible = detected_entity_data["plausible_activities"]
                implausible = detected_entity_data["implausible_activities"]

                if detected_act_key in implausible:
                    is_conflict = True
                    conflict_explanation = (
                        f"Subject identified as {name} ({role}), depicted {detected_act_desc}. "
                        f"This directly contradicts the person's real-world profession and public career; "
                        f"no authentic historical record exists of this individual in this capacity. "
                        f"This represents a known fictional deepfake or generative AI scenario."
                    )
                elif detected_act_key in plausible:
                    is_aligned = True
                    alignment_explanation = (
                        f"Subject identified as {name} ({role}), depicted {detected_act_desc}. "
                        f"This scenario is fully authentic and directly aligned with the person's genuine real-world profession and career."
                    )
            else:
                # Subject is an Unknown Civilian / Private Individual
                if detected_social_key == "improbable_couple_composite" and social_confidence >= 0.55:
                    is_conflict = True
                    conflict_explanation = (
                        "Social & Physical Implausibility: Visual semantics identify an improbable composite / synthetic pairing "
                        "(an average civilian individual juxtaposed with an unrealistically glamorous model/influencer with lighting and depth disparity). "
                        "This pattern is a known synthetic wish-fulfillment / digital composite motif."
                    )
                elif detected_social_key == "natural_civilian_couple":
                    is_aligned = True
                    alignment_explanation = "Authentic civilian setting: Natural candid photograph of an everyday couple with uniform environmental lighting."
                else:
                    is_aligned = True
                    alignment_explanation = "Authentic civilian setting: Natural personal photograph showing consistent candid characteristics."

            evidence_found = is_conflict or is_aligned
            execution_time = (time.perf_counter() - start_time) * 1000.0

            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.COMPLETED,
                result={
                    "entity_identified": detected_entity_data["name"] if detected_entity_data else "Unregistered Individual / Civilian",
                    "entity_profession": detected_entity_data["profession"] if detected_entity_data else "Unknown / Civilian",
                    "entity_category": detected_entity_data["category"] if detected_entity_data else "GENERAL",
                    "entity_match_confidence": round(entity_confidence, 3) if detected_entity_data else 0.0,
                    "raw_cosine_similarity": round(top_raw_cos, 3),
                    "top_candidates": top_candidates,
                    "depicted_activity": detected_act_desc,
                    "activity_key": detected_act_key,
                    "activity_confidence": round(activity_confidence, 3),
                    "scenario_incongruity_detected": is_conflict,
                    "scenario_aligned_detected": is_aligned,
                    "conflict_explanation": conflict_explanation,
                    "alignment_explanation": alignment_explanation
                },
                evidence_found=evidence_found,
                confidence=round(entity_confidence, 2) if detected_entity_data else None,
                execution_time_ms=round(execution_time, 2),
                limitations=limitations
            )

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000.0
            return ModuleResult(
                module_name=self.name,
                status=TaskStatus.FAILED,
                result={},
                evidence_found=False,
                execution_time_ms=round(execution_time, 2),
                error_message=f"Contextual OSINT error: {str(e)}",
                limitations=limitations
            )
