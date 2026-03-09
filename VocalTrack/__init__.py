# Import os module for environment variable manipulation
import os
# Import warnings module to suppress unwanted warning messages
import warnings

# Suppress pygame support prompt and pkg_resources deprecation warning
# Set environment variable to hide pygame's startup message banner
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Configure warnings filter to ignore pkg_resources deprecation warnings
warnings.filterwarnings(
	"ignore",  # Action to take (ignore the warning completely)
	message=r"pkg_resources is deprecated as an API.*",  # Regex pattern matching deprecation message
	category=UserWarning,  # Type of warning to filter (UserWarning class)
)

# Lazy imports to avoid circular dependencies
# Define special attribute getter for dynamic imports (called when accessing undefined attributes)
def __getattr__(name):
	# Check if requested attribute is "LiveVowel"
	if name == "LiveVowel":
		# Import LiveVowel class from LiveVowel module (deferred until first use)
		from .LiveVowel import LiveVowel
		# Return the LiveVowel class object
		return LiveVowel
	# Check if requested attribute is "LivePitch"
	elif name == "LivePitch":
		# Import LivePitch class from LivePitch module (deferred until first use)
		from .LivePitch import LivePitch
		# Return the LivePitch class object
		return LivePitch
	# If attribute name doesn't match known exports, raise standard attribute error
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Define public API - list of names that should be exported from this module
__all__ = ["LiveVowel", "LivePitch", "config"]
