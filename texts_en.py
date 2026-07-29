# Common text variables
WELCOME_NEW_USER = "Hi! I'm the WG Black Market channel bot. I will post ads on your behalf, and if you want to change or unpublish something later, you can come to me for that too."
START_MINIAPP_MESSAGE = "Now Baraholka is an app, not a bot. Open the app using the button below."
START_NEW_AD = "Send the text of your ad. Next I'll ask for the price and photos. But first — tell me what you want to sell or buy."
CHOOSE_ACTION = "Something went wrong, but no worries. Let's start over?"
NEW_AD_CHOICE = "Fresh crispy ad"
MY_ADS_CHOICE = "My ads"
USER_ADS_MESSAGE = "📢 *Your ads:*"
CHOOSE_ACTION_NEW = "What do we do?"
PREVIEW_TEXT = "Here is how it will look\\."
SUBSCRIPTION_SUCCESS = "Thanks for subscribing! 💃🏻"
NOT_SUBSCRIBED_YET = "You haven't subscribed to the channel yet. Please subscribe and press 'I have subscribed'."
ADD_PHOTO_TEXT = "Got the photo! You can add more if you want."
SEND_PHOTO_OR_FINISH_OR_NO_PHOTO = "Please send a photo or press 'Ad without photos'."
MAX_PHOTOS_REACHED = "Wow. That's a lot of photos. One ad can contain at most 10 photos, so some weren't saved."
NO_PHOTO_AD = "Ad without photos"
PROCESSING_PHOTOS = "One moment, assembling photos into an album"
PRICE_TEXT = "*Price*"
CONTACT_TEXT = "*Who to contact*"
UPDATED_TEXT = "🆙 _Updated: {current_time}_"
FINISH_PHOTO_UPLOAD = "Done with photos, let's continue"
POST_SUCCESS_MESSAGE = "💥 *Success\\! Here is the link to your ad:*\n[Open ad]({link})"
POST_FAILURE_MESSAGE = "An error occurred while posting the ad"
EDIT_DESCRIPTION_PROMPT = "Sure. Send the new ad text."
EDIT_PRICE_PROMPT = "Ok! What will the new price be?"
EDIT_PHOTOS_PROMPT = "Easy! Send new photos.\n\nIf you need to delete them, press “Done with photos” right away and I will remove all attached ones."

NO_ANNOUNCEMENTS_MESSAGE = "You don't have any ads yet."
ANNOUNCEMENT_LIST_MESSAGE = "{description}\n\n*Price*\n{price}"
CANCEL_MESSAGE = "Ok, canceled."

ASK_FOR_PHOTOS = "And now — photos\\! You can send several at once\\.\n\n_I don't accept hi\\-res, so don't uncheck the “Compress photos” setting\\._"
ADD_NEW_PHOTOS = "📸 Send new photos. You can upload up to 10 photos."
OLD_PHOTOS_DELETED = "All old photos have been deleted. Send new photos."
HAS_PHOTOS = "📸 You already have uploaded photos. Do you want to add new ones or replace the current ones?"

NO_ANN_ID_MESSAGE_ERROR = "Error: ad ID not found."

SUBSCRIBE_PROMPT = "Please subscribe to our channel to continue."
SUBSCRIBE_BUTTON = "I have subscribed"
MAIN_MENU_BUTTON = "Main menu"
OPEN_WEBAPP_BUTTON = "Open Application"

LANG_MESSAGE = "Client language: {language_code}"
LANG_UNKNOWN = "Couldn't determine client language."

ERROR_ANN_ID_NOT_FOUND = "❌ Error: ad ID not found."
ERROR_ANNOUNCEMENT_NOT_FOUND = "❌ Error: ad not found in the database."
ERROR_NO_ANNOUNCEMENTS = "Error: no ads found."
ERROR_USER_DATA_NOT_FOUND = "❌ Error: failed to get user data."

EDIT_MENU_TITLE = "What do we change?"
EDIT_DESCRIPTION_BUTTON = "📝 Ad text"
EDIT_PRICE_BUTTON = "💰 Price"
EDIT_PHOTOS_BUTTON = "🖼️ Photos"
EDIT_CANCEL_BUTTON = "🚫 No changes"

ASK_PHOTO_ACTION_ADD = "➕ Add to existing"
ASK_PHOTO_ACTION_REPLACE = "🔄 Replace all"
ASK_PHOTO_ACTION_SKIP = "🚫 Skip"

PREVIEW_EDIT_BUTTON = "✏️ Edit"
PREVIEW_PUBLISH_BUTTON = "📢 Publish"
DELETE_BUTTON = "❌ Delete"

DRAFT_STATUS = "📝 _Draft_\n"
PUBLISHED_STATUS = "[Published 📌]({link})\n"

DESCRIPTION_TOO_LONG = "❗ Description is too long. Maximum 800 characters. Now: {length} characters.\nPlease shorten the text."
PRICE_TOO_LONG = "❗ Price is too long. Maximum 130 characters. Now: {length} characters.\nPlease shorten the text."
ACCEPTED_PRICE_PROMPT = "Got it! Now enter the price."

NOT_SUBSCRIBED_SHORT = "You are not subscribed to the channel yet."

ANONYMOUS_NAME = "Anonymous"

# --- Dates ---
# Short month names for readable dates: "29 Jul, 15:18".
MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# --- Auction (channel post) ---
AUCTION_HEADER = "💰 AUCTION"
AUCTION_FINISHED_HEADER = "✅ AUCTION ENDED"
AUCTION_START_PRICE = "Starting price"
AUCTION_CURRENT_BID = "Current bid"
AUCTION_NO_BIDS_YET = "No bids yet"
AUCTION_MIN_STEP = "Minimum step"
AUCTION_BUYOUT_PRICE = "Buy now"
AUCTION_END_AT = "Auction until"
AUCTION_FINAL_PRICE = "Final price"
AUCTION_WINNER = "Winner"
AUCTION_NO_BIDS_PLACED = "No bids were placed"
AUCTION_BID_LINK_LABEL = "👉 PLACE A BID 👈"

# --- Auction (owner notification about a new bid) ---
AUCTION_NEW_BID_TITLE = "🔨 New bid on your auction!"
AUCTION_NEW_BID_AMOUNT = "Bid"
AUCTION_NEW_BID_FROM = "From"
AUCTION_NEW_BID_TOTAL = "Total bids"
AUCTION_VIEW_BIDS_BUTTON = "📊 View bids"

# --- Auction (outbid notification) ---
AUCTION_OUTBID_MESSAGE = "🔔 You've been outbid!\n\n{desc}\n\nCurrent bid: {amount}\nListing: {link}"
AUCTION_OUTBID_BUTTON = "🔼 Raise your bid"

# --- Auction (anti-sniping: a bid in the final minutes extends the auction) ---
AUCTION_EXTENDED_NOTE = "⏱ Bid in the last {minutes} min — auction extended until {until}"

# --- Auction (finish) ---
AUCTION_SELLER_FINISHED_WIN = "Auction ended!\nWinner: {winner}\nFinal price: {price}\nListing: {link}"
AUCTION_SELLER_FINISHED_NOBIDS = "Auction ended.\nNo bids were placed.\nListing: {link}"
AUCTION_WINNER_FINISHED = "You won the auction!\nYour bid: {price}\nContact the seller: {seller_contact}\nListing: {link}"
