"""Support for the Google Cloud TTS service."""

import logging
import os

from google.api_core.exceptions import GoogleAPIError
from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.tts import (
    CONF_LANG,
    PLATFORM_SCHEMA as TTS_PLATFORM_SCHEMA,
    Provider,
    Voice,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .helpers import async_tts_voices

_LOGGER = logging.getLogger(__name__)

CONF_KEY_FILE = "key_file"
CONF_GENDER = "gender"
CONF_VOICE = "voice"
CONF_ENCODING = "encoding"
CONF_SPEED = "speed"
CONF_PITCH = "pitch"
CONF_GAIN = "gain"
CONF_PROFILES = "profiles"
CONF_TEXT_TYPE = "text_type"

DEFAULT_LANG = "en-US"

DEFAULT_GENDER = "NEUTRAL"

LANG_REGEX = r"[a-z]{2,3}-[A-Z]{2}|"
VOICE_REGEX = r"[a-z]{2,3}-[A-Z]{2}-.*-[A-Z]|"
DEFAULT_VOICE = ""

DEFAULT_ENCODING = "MP3"

MIN_SPEED = 0.25
MAX_SPEED = 4.0
DEFAULT_SPEED = 1.0

MIN_PITCH = -20.0
MAX_PITCH = 20.0
DEFAULT_PITCH = 0

MIN_GAIN = -96.0
MAX_GAIN = 16.0
DEFAULT_GAIN = 0

SUPPORTED_TEXT_TYPES = ["text", "ssml"]
DEFAULT_TEXT_TYPE = "text"

SUPPORTED_PROFILES = [
    "wearable-class-device",
    "handset-class-device",
    "headphone-class-device",
    "small-bluetooth-speaker-class-device",
    "medium-bluetooth-speaker-class-device",
    "large-home-entertainment-class-device",
    "large-automotive-class-device",
    "telephony-class-application",
]

SUPPORTED_OPTIONS = [
    CONF_VOICE,
    CONF_GENDER,
    CONF_ENCODING,
    CONF_SPEED,
    CONF_PITCH,
    CONF_GAIN,
    CONF_PROFILES,
    CONF_TEXT_TYPE,
]

GENDER_SCHEMA = vol.All(vol.Upper, vol.In(texttospeech.SsmlVoiceGender.__members__))
VOICE_SCHEMA = cv.matches_regex(VOICE_REGEX)
SCHEMA_ENCODING = vol.All(vol.Upper, vol.In(texttospeech.AudioEncoding.__members__))
SPEED_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_SPEED, max=MAX_SPEED))
PITCH_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_PITCH, max=MAX_PITCH))
GAIN_SCHEMA = vol.All(vol.Coerce(float), vol.Clamp(min=MIN_GAIN, max=MAX_GAIN))
PROFILES_SCHEMA = vol.All(cv.ensure_list, [vol.In(SUPPORTED_PROFILES)])
TEXT_TYPE_SCHEMA = vol.All(vol.Lower, vol.In(SUPPORTED_TEXT_TYPES))

PLATFORM_SCHEMA = TTS_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_KEY_FILE): cv.string,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): cv.matches_regex(LANG_REGEX),
        vol.Optional(CONF_GENDER, default=DEFAULT_GENDER): GENDER_SCHEMA,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): VOICE_SCHEMA,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): SCHEMA_ENCODING,
        vol.Optional(CONF_SPEED, default=DEFAULT_SPEED): SPEED_SCHEMA,
        vol.Optional(CONF_PITCH, default=DEFAULT_PITCH): PITCH_SCHEMA,
        vol.Optional(CONF_GAIN, default=DEFAULT_GAIN): GAIN_SCHEMA,
        vol.Optional(CONF_PROFILES, default=[]): PROFILES_SCHEMA,
        vol.Optional(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): TEXT_TYPE_SCHEMA,
    }
)


async def async_get_engine(hass, config, discovery_info=None):
    """Set up Google Cloud TTS component."""
    if key_file := config.get(CONF_KEY_FILE):
        key_file = hass.config.path(key_file)
        if not os.path.isfile(key_file):
            _LOGGER.error("File %s doesn't exist", key_file)
            return None
    if key_file:
        client = texttospeech.TextToSpeechAsyncClient.from_service_account_json(
            key_file
        )
    else:
        client = texttospeech.TextToSpeechAsyncClient()
    try:
        voices = await async_tts_voices(client)
    except GoogleAPIError as err:
        _LOGGER.error("Error from calling list_voices: %s", err)
        return None
    return GoogleCloudTTSProvider(
        hass,
        client,
        voices,
        config[CONF_LANG],
        config[CONF_GENDER],
        config[CONF_VOICE],
        config[CONF_ENCODING],
        config[CONF_SPEED],
        config[CONF_PITCH],
        config[CONF_GAIN],
        config[CONF_PROFILES],
        config[CONF_TEXT_TYPE],
    )


class GoogleCloudTTSProvider(Provider):
    """The Google Cloud TTS API provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: texttospeech.TextToSpeechAsyncClient,
        voices: dict[str, list[str]],
        language=DEFAULT_LANG,
        gender=DEFAULT_GENDER,
        voice=DEFAULT_VOICE,
        encoding=DEFAULT_ENCODING,
        speed=1.0,
        pitch=0,
        gain=0,
        profiles=None,
        text_type=DEFAULT_TEXT_TYPE,
    ) -> None:
        """Init Google Cloud TTS service."""
        self.hass = hass
        self.name = "Google Cloud TTS"
        self._client = client
        self._voices = voices
        self._language = language
        self._gender = gender
        self._voice = voice
        self._encoding = encoding
        self._speed = speed
        self._pitch = pitch
        self._gain = gain
        self._profiles = profiles
        self._text_type = text_type

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return list(self._voices)

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_options(self):
        """Return a list of supported options."""
        return SUPPORTED_OPTIONS

    @property
    def default_options(self):
        """Return a dict including default options."""
        return {
            CONF_GENDER: self._gender,
            CONF_VOICE: self._voice,
            CONF_ENCODING: self._encoding,
            CONF_SPEED: self._speed,
            CONF_PITCH: self._pitch,
            CONF_GAIN: self._gain,
            CONF_PROFILES: self._profiles,
            CONF_TEXT_TYPE: self._text_type,
        }

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        if not (voices := self._voices.get(language)):
            return None
        return [Voice(voice, voice) for voice in voices]

    async def async_get_tts_audio(self, message, language, options):
        """Load TTS from google."""
        options_schema = vol.Schema(
            {
                vol.Optional(CONF_GENDER, default=self._gender): GENDER_SCHEMA,
                vol.Optional(CONF_VOICE, default=self._voice): VOICE_SCHEMA,
                vol.Optional(CONF_ENCODING, default=self._encoding): SCHEMA_ENCODING,
                vol.Optional(CONF_SPEED, default=self._speed): SPEED_SCHEMA,
                vol.Optional(CONF_PITCH, default=self._pitch): PITCH_SCHEMA,
                vol.Optional(CONF_GAIN, default=self._gain): GAIN_SCHEMA,
                vol.Optional(CONF_PROFILES, default=self._profiles): PROFILES_SCHEMA,
                vol.Optional(CONF_TEXT_TYPE, default=self._text_type): TEXT_TYPE_SCHEMA,
            }
        )
        try:
            options = options_schema(options)
        except vol.Invalid as err:
            _LOGGER.error("Error: %s when validating options: %s", err, options)
            return None, None

        encoding = texttospeech.AudioEncoding[options[CONF_ENCODING]]
        gender = texttospeech.SsmlVoiceGender[options[CONF_GENDER]]
        voice = options[CONF_VOICE]
        if voice:
            gender = None
            if not voice.startswith(language):
                language = voice[:5]

        request = texttospeech.SynthesizeSpeechRequest(
            input=texttospeech.SynthesisInput(**{options[CONF_TEXT_TYPE]: message}),
            voice=texttospeech.VoiceSelectionParams(
                language_code=language,
                ssml_gender=gender,
                name=voice,
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=encoding,
                speaking_rate=options[CONF_SPEED],
                pitch=options[CONF_PITCH],
                volume_gain_db=options[CONF_GAIN],
                effects_profile_id=options[CONF_PROFILES],
            ),
        )

        try:
            response = await self._client.synthesize_speech(request, timeout=10)
        except GoogleAPIError as err:
            _LOGGER.error("Error occurred during Google Cloud TTS call: %s", err)
            return None, None

        if encoding == texttospeech.AudioEncoding.MP3:
            extension = "mp3"
        elif encoding == texttospeech.AudioEncoding.OGG_OPUS:
            extension = "ogg"
        else:
            extension = "wav"

        return extension, response.audio_content
