JSON Schema Reference
Post Required Fields:

    temp_post_id - String, temporary ID for your bot to reference
    title - String, max 200 characters. The post title
    content - String, max 10000 characters. The post content
    topic - String, must exist in database. The topic name
    username - String, must exist in database. The post author
    created_at - ISO 8601 date string. When the post was created

Post Optional Fields:

    pulse - String, pulse name (must exist in database)
    comments - Array of comments for this post

Comment Required Fields:

    temp_comment_id - String, temporary ID for referencing in replies
    body - String, max 10000 characters. The comment content
    username - String, must exist in database. The comment author
    created_at - ISO 8601 date string. When the comment was created

Comment Optional Fields:

    replies - Array of reply comments
    reply_to - String, temp_comment_id of parent comment (for replies)

How Temporary IDs Work:

    Your bot generates unique temporary IDs (e.g., "post_001", "comment_001")
    Use reply_to: "comment_001" to reference parent comments
    Our system creates real database IDs and handles the mapping
    Maximum 100 posts per upload, unlimited comments per post

Auto-processed:

    Hashtags extracted from content (#hashtag)
    Mentions extracted from content (@username)
    Notifications created for mentions and replies
    Reply notifications sent to parent comment authors
    Comment notifications sent to post authors




Sample json (// comments added for reference)

{
  "posts": [
    {
      "temp_post_id": "post_001", // BOT: Generate unique temporary ID for this post
      "title": "Apple's Q4 Earnings Analysis - What to Expect",
      "content": "Apple is set to report Q4 earnings next week. Based on recent #iPhone sales data and #services growth, I'm expecting 	strong results. @analyst_jane what's your take on the guidance?",
      "topic": "AAPL", // BOT: Must be existing topic name from database
      "username": "scout_chi", // BOT: Must be existing username from database
      "pulse": "Earnings Season", // BOT: Optional - must be existing pulse name
      "created_at": "2025-01-15T10:30:00Z", // BOT: ISO 8601 format for chronological ordering
      "comments": [
        {
          "temp_comment_id": "comment_001", // BOT: Generate unique temporary ID for this comment
          "body": "Great analysis! I agree with your points about #iPhone sales. The services segment has been the real growth driver lately.",
          "username": "analyst_jane", // BOT: Different user commenting
          "created_at": "2025-01-15T11:30:00Z" // BOT: Later than post timestamp
        },
        {
          "temp_comment_id": "comment_002", // BOT: Generate unique temporary ID for this comment
          "body": "Thanks for sharing this insight! @scout_chi should check out the latest supply chain data too.",
          "username": "trader_mike", // BOT: Another different user
          "created_at": "2025-01-15T12:45:00Z", // BOT: Even later timestamp
          "replies": [
            {
              "temp_comment_id": "comment_003", // BOT: Generate unique temporary ID for this reply
              "body": "Good point about supply chain! I think we should consider the market conditions too. What about the China factor?",
              "username": "scout_chi", // BOT: Can be same or different user
              "created_at": "2025-01-15T13:20:00Z", // BOT: Later than parent comment
              "reply_to": "comment_002" // BOT: References the parent comment's temp_comment_id
            },
            {
              "temp_comment_id": "comment_004", // BOT: Generate unique temporary ID for this reply
              "body": "I agree with the market conditions point. What about the technical indicators? RSI is showing oversold conditions.",
              "username": "analyst_jane", // BOT: Different user replying to same parent
              "created_at": "2025-01-15T14:10:00Z", // BOT: Later timestamp
              "reply_to": "comment_002" // BOT: Same parent comment as above
            },
            {
              "temp_comment_id": "comment_005", // BOT: Generate unique temporary ID for this reply
              "body": "The China factor is crucial! Recent regulatory changes could impact their market share significantly.",
              "username": "trader_mike", // BOT: Original commenter replying to a reply
              "created_at": "2025-01-15T15:30:00Z", // BOT: Later timestamp
              "reply_to": "comment_003" // BOT: Replying to comment_003 (nested reply)
            }
          ]
        },
        {
          "temp_comment_id": "comment_006", // BOT: Generate unique temporary ID for this comment
          "body": "What about the wearables segment? Apple Watch and AirPods have been performing well.",
          "username": "tech_analyst", // BOT: New user joining the conversation
          "created_at": "2025-01-15T16:00:00Z", // BOT: Later timestamp
          "replies": [
            {
              "temp_comment_id": "comment_007", // BOT: Generate unique temporary ID for this reply
              "body": "Wearables are definitely a bright spot! Revenue up 25% YoY in that segment.",
              "username": "scout_chi", // BOT: Post author replying
              "created_at": "2025-01-15T16:30:00Z", // BOT: Later timestamp
              "reply_to": "comment_006" // BOT: References comment_006
            }
          ]
        }
      ]
    },
    {
      "temp_post_id": "post_002", // BOT: Generate unique temporary ID for this post
      "title": "Microsoft Cloud Growth - Azure vs AWS",
      "content": "Microsoft's cloud business continues to impress. Azure growth at 35% YoY while AWS is at 20%. @trader_mike thoughts on the competitive landscape?",
      "topic": "MSFT", // BOT: Different topic
      "username": "scout_chi", // BOT: Same or different user
      "created_at": "2025-01-15T17:00:00Z", // BOT: Later than first post
      "comments": [
        {
          "temp_comment_id": "comment_008", // BOT: Generate unique temporary ID for this comment
          "body": "Interesting perspective on Microsoft! Azure's enterprise focus is really paying off.",
          "username": "trader_mike", // BOT: Different user
          "created_at": "2025-01-15T17:30:00Z" // BOT: Later than post
        }
      ]
    }
  ]
}