Search.setIndex({docnames:["index","pymap.concurrent","pymap.config","pymap.exceptions","pymap.flags","pymap.interfaces","pymap.keyval","pymap.keyval.dict","pymap.keyval.maildir","pymap.listtree","pymap.mailbox","pymap.message","pymap.parsing","pymap.proxy","pymap.search","pymap.selected","pymap.server","pymap.sockinfo","pymap.state"],envversion:{"sphinx.domains.c":1,"sphinx.domains.changeset":1,"sphinx.domains.cpp":1,"sphinx.domains.javascript":1,"sphinx.domains.math":2,"sphinx.domains.python":1,"sphinx.domains.rst":1,"sphinx.domains.std":1,"sphinx.ext.intersphinx":1,sphinx:55},filenames:["index.rst","pymap.concurrent.rst","pymap.config.rst","pymap.exceptions.rst","pymap.flags.rst","pymap.interfaces.rst","pymap.keyval.rst","pymap.keyval.dict.rst","pymap.keyval.maildir.rst","pymap.listtree.rst","pymap.mailbox.rst","pymap.message.rst","pymap.parsing.rst","pymap.proxy.rst","pymap.search.rst","pymap.selected.rst","pymap.server.rst","pymap.sockinfo.rst","pymap.state.rst"],objects:{"pymap.concurrent":{Event:[1,1,1,""],FileLock:[1,1,1,""],ReadWriteLock:[1,1,1,""],TimeoutError:[1,5,1,""]},"pymap.concurrent.Event":{clear:[1,2,1,""],for_asyncio:[1,3,1,""],for_threading:[1,3,1,""],is_set:[1,2,1,""],or_event:[1,2,1,""],set:[1,2,1,""],subsystem:[1,4,1,""],wait:[1,2,1,""]},"pymap.concurrent.FileLock":{read_lock:[1,2,1,""],subsystem:[1,4,1,""],write_lock:[1,2,1,""]},"pymap.concurrent.ReadWriteLock":{for_asyncio:[1,3,1,""],for_threading:[1,3,1,""],read_lock:[1,2,1,""],subsystem:[1,4,1,""],write_lock:[1,2,1,""]},"pymap.config":{IMAPConfig:[2,1,1,""]},"pymap.config.IMAPConfig":{args:[2,4,1,""],from_args:[2,3,1,""],parse_args:[2,3,1,""]},"pymap.exceptions":{AppendFailure:[3,5,1,""],CloseConnection:[3,5,1,""],CommandNotAllowed:[3,5,1,""],InvalidAuth:[3,5,1,""],MailboxConflict:[3,5,1,""],MailboxError:[3,5,1,""],MailboxHasChildren:[3,5,1,""],MailboxNotFound:[3,5,1,""],MailboxReadOnly:[3,5,1,""],ResponseError:[3,5,1,""],SearchNotAllowed:[3,5,1,""]},"pymap.exceptions.CloseConnection":{get_response:[3,2,1,""]},"pymap.exceptions.CommandNotAllowed":{get_response:[3,2,1,""]},"pymap.exceptions.InvalidAuth":{get_response:[3,2,1,""]},"pymap.exceptions.MailboxError":{get_response:[3,2,1,""]},"pymap.exceptions.ResponseError":{get_response:[3,2,1,""]},"pymap.flags":{FlagOp:[4,1,1,""],SessionFlags:[4,1,1,""]},"pymap.flags.FlagOp":{ADD:[4,4,1,""],DELETE:[4,4,1,""],REPLACE:[4,4,1,""]},"pymap.flags.SessionFlags":{add_recent:[4,2,1,""],count_recent:[4,2,1,""],get:[4,2,1,""],remove:[4,2,1,""],update:[4,2,1,""]},"pymap.interfaces":{mailbox:[5,0,0,"-"],message:[5,0,0,"-"],session:[5,0,0,"-"]},"pymap.interfaces.mailbox":{MailboxInterface:[5,1,1,""]},"pymap.interfaces.mailbox.MailboxInterface":{exists:[5,4,1,""],first_unseen:[5,4,1,""],flags:[5,4,1,""],name:[5,4,1,""],next_uid:[5,4,1,""],permanent_flags:[5,4,1,""],readonly:[5,4,1,""],recent:[5,4,1,""],session_flags:[5,4,1,""],uid_validity:[5,4,1,""],unseen:[5,4,1,""]},"pymap.interfaces.message":{Header:[5,1,1,""],LoadedMessage:[5,1,1,""],Message:[5,1,1,""]},"pymap.interfaces.message.LoadedMessage":{get_body:[5,2,1,""],get_body_structure:[5,2,1,""],get_envelope_structure:[5,2,1,""],get_header:[5,2,1,""],get_headers:[5,2,1,""],get_size:[5,2,1,""],get_text:[5,2,1,""]},"pymap.interfaces.message.Message":{copy:[5,2,1,""],get_flags:[5,2,1,""],internal_date:[5,4,1,""],permanent_flags:[5,4,1,""],uid:[5,4,1,""],update_flags:[5,2,1,""]},"pymap.interfaces.session":{LoginProtocol:[5,1,1,""],SessionInterface:[5,1,1,""]},"pymap.interfaces.session.LoginProtocol":{__call__:[5,2,1,""]},"pymap.interfaces.session.SessionInterface":{append_messages:[5,2,1,""],check_mailbox:[5,2,1,""],copy_messages:[5,2,1,""],create_mailbox:[5,2,1,""],delete_mailbox:[5,2,1,""],expunge_mailbox:[5,2,1,""],fetch_messages:[5,2,1,""],get_mailbox:[5,2,1,""],list_mailboxes:[5,2,1,""],rename_mailbox:[5,2,1,""],search_mailbox:[5,2,1,""],select_mailbox:[5,2,1,""],subscribe:[5,2,1,""],unsubscribe:[5,2,1,""],update_flags:[5,2,1,""]},"pymap.keyval":{dict:[7,0,0,"-"],mailbox:[6,0,0,"-"],maildir:[8,0,0,"-"],session:[6,0,0,"-"],util:[6,0,0,"-"]},"pymap.keyval.dict":{Config:[7,1,1,""],Mailbox:[7,1,1,""],Message:[7,1,1,""],Session:[7,1,1,""]},"pymap.keyval.dict.Config":{demo_password:[7,4,1,""],demo_user:[7,4,1,""],parse_args:[7,3,1,""]},"pymap.keyval.dict.Session":{get_password:[7,3,1,""],login:[7,3,1,""]},"pymap.keyval.mailbox":{KeyValMailbox:[6,1,1,""],KeyValMessage:[6,1,1,""]},"pymap.keyval.maildir":{Config:[8,1,1,""],Mailbox:[8,1,1,""],Message:[8,1,1,""],Session:[8,1,1,""],flags:[8,0,0,"-"],layout:[8,0,0,"-"],subscriptions:[8,0,0,"-"],uidlist:[8,0,0,"-"]},"pymap.keyval.maildir.Config":{mailbox_delimiter:[8,4,1,""],parse_args:[8,3,1,""],users_file:[8,4,1,""]},"pymap.keyval.maildir.Session":{find_user:[8,3,1,""],login:[8,3,1,""]},"pymap.keyval.maildir.flags":{MaildirFlags:[8,1,1,""]},"pymap.keyval.maildir.flags.MaildirFlags":{from_maildir:[8,2,1,""],keywords:[8,4,1,""],permanent_flags:[8,4,1,""],system_flags:[8,4,1,""],to_maildir:[8,2,1,""]},"pymap.keyval.maildir.layout":{DefaultLayout:[8,1,1,""],FilesystemLayout:[8,1,1,""],MaildirLayout:[8,1,1,""]},"pymap.keyval.maildir.layout.MaildirLayout":{add_folder:[8,2,1,""],delimiter:[8,4,1,""],get:[8,3,1,""],get_folder:[8,2,1,""],get_path:[8,2,1,""],list_folders:[8,2,1,""],path:[8,4,1,""],remove_folder:[8,2,1,""],rename_folder:[8,2,1,""]},"pymap.keyval.maildir.subscriptions":{Subscriptions:[8,1,1,""]},"pymap.keyval.maildir.subscriptions.Subscriptions":{add:[8,2,1,""],remove:[8,2,1,""],set:[8,2,1,""],subscribed:[8,4,1,""]},"pymap.keyval.maildir.uidlist":{Record:[8,1,1,""],UidList:[8,1,1,""]},"pymap.keyval.maildir.uidlist.Record":{fields:[8,4,1,""],filename:[8,4,1,""],uid:[8,4,1,""]},"pymap.keyval.maildir.uidlist.UidList":{FILE_NAME:[8,4,1,""],LOCK_FILE:[8,4,1,""],get:[8,2,1,""],records:[8,4,1,""],remove:[8,2,1,""],set:[8,2,1,""]},"pymap.keyval.session":{KeyValSession:[6,1,1,""]},"pymap.keyval.session.KeyValSession":{append_messages:[6,2,1,""],check_mailbox:[6,2,1,""],copy_messages:[6,2,1,""],create_mailbox:[6,2,1,""],delete_mailbox:[6,2,1,""],expunge_mailbox:[6,2,1,""],fetch_messages:[6,2,1,""],get_mailbox:[6,2,1,""],list_mailboxes:[6,2,1,""],rename_mailbox:[6,2,1,""],search_mailbox:[6,2,1,""],select_mailbox:[6,2,1,""],subscribe:[6,2,1,""],unsubscribe:[6,2,1,""],update_flags:[6,2,1,""]},"pymap.keyval.util":{asyncenumerate:[6,6,1,""]},"pymap.listtree":{ListEntry:[9,1,1,""],ListTree:[9,1,1,""]},"pymap.listtree.ListEntry":{attrs:[9,4,1,""],exists:[9,4,1,""],has_children:[9,4,1,""],name:[9,4,1,""]},"pymap.listtree.ListTree":{list:[9,2,1,""],list_matching:[9,2,1,""],update:[9,2,1,""]},"pymap.mailbox":{MailboxSnapshot:[10,1,1,""]},"pymap.mailbox.MailboxSnapshot":{exists:[10,4,1,""],first_unseen:[10,4,1,""],flags:[10,4,1,""],name:[10,4,1,""],new_uid_validity:[10,3,1,""],next_uid:[10,4,1,""],permanent_flags:[10,4,1,""],readonly:[10,4,1,""],recent:[10,4,1,""],session_flags:[10,4,1,""],uid_validity:[10,4,1,""],unseen:[10,4,1,""]},"pymap.message":{AppendMessage:[11,1,1,""],BaseLoadedMessage:[11,1,1,""],BaseMessage:[11,1,1,""]},"pymap.message.AppendMessage":{flag_set:[11,4,1,""],message:[11,4,1,""],options:[11,4,1,""],when:[11,4,1,""]},"pymap.message.BaseLoadedMessage":{contents:[11,4,1,""],copy:[11,2,1,""],get_body:[11,2,1,""],get_body_structure:[11,2,1,""],get_envelope_structure:[11,2,1,""],get_header:[11,2,1,""],get_headers:[11,2,1,""],get_size:[11,2,1,""],get_text:[11,2,1,""],parse:[11,3,1,""]},"pymap.message.BaseMessage":{copy:[11,2,1,""],get_flags:[11,2,1,""],internal_date:[11,4,1,""],permanent_flags:[11,4,1,""],uid:[11,4,1,""],update_flags:[11,2,1,""]},"pymap.parsing":{EndLine:[12,1,1,""],ExpectedParseable:[12,1,1,""],Params:[12,1,1,""],Parseable:[12,1,1,""],Space:[12,1,1,""],command:[12,0,0,"-"],commands:[12,0,0,"-"],exceptions:[12,0,0,"-"],primitives:[12,0,0,"-"],response:[12,0,0,"-"]},"pymap.parsing.EndLine":{carriage_return:[12,4,1,""],parse:[12,3,1,""],preceding_spaces:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.ExpectedParseable":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.Params":{copy:[12,2,1,""]},"pymap.parsing.Parseable":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.Space":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.command":{Command:[12,1,1,""],CommandAny:[12,1,1,""],CommandAuth:[12,1,1,""],CommandNoArgs:[12,1,1,""],CommandNonAuth:[12,1,1,""],CommandSelect:[12,1,1,""],any:[12,0,0,"-"],auth:[12,0,0,"-"],nonauth:[12,0,0,"-"],select:[12,0,0,"-"]},"pymap.parsing.command.Command":{command:[12,4,1,""],compound:[12,4,1,""],delegate:[12,4,1,""],parse:[12,3,1,""],tag:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.command.CommandAny":{parse:[12,3,1,""]},"pymap.parsing.command.CommandAuth":{parse:[12,3,1,""]},"pymap.parsing.command.CommandNoArgs":{parse:[12,3,1,""]},"pymap.parsing.command.CommandNonAuth":{parse:[12,3,1,""]},"pymap.parsing.command.CommandSelect":{parse:[12,3,1,""]},"pymap.parsing.command.any":{CapabilityCommand:[12,1,1,""],LogoutCommand:[12,1,1,""],NoOpCommand:[12,1,1,""]},"pymap.parsing.command.auth":{AppendCommand:[12,1,1,""],CreateCommand:[12,1,1,""],DeleteCommand:[12,1,1,""],ExamineCommand:[12,1,1,""],LSubCommand:[12,1,1,""],ListCommand:[12,1,1,""],RenameCommand:[12,1,1,""],SelectCommand:[12,1,1,""],StatusCommand:[12,1,1,""],SubscribeCommand:[12,1,1,""],UnsubscribeCommand:[12,1,1,""]},"pymap.parsing.command.auth.AppendCommand":{parse:[12,3,1,""]},"pymap.parsing.command.auth.CreateCommand":{parse:[12,3,1,""]},"pymap.parsing.command.auth.ExamineCommand":{delegate:[12,4,1,""],readonly:[12,4,1,""]},"pymap.parsing.command.auth.LSubCommand":{delegate:[12,4,1,""],only_subscribed:[12,4,1,""]},"pymap.parsing.command.auth.ListCommand":{only_subscribed:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.auth.RenameCommand":{parse:[12,3,1,""]},"pymap.parsing.command.auth.SelectCommand":{parse:[12,3,1,""],readonly:[12,4,1,""]},"pymap.parsing.command.auth.StatusCommand":{parse:[12,3,1,""]},"pymap.parsing.command.nonauth":{AuthenticateCommand:[12,1,1,""],LoginCommand:[12,1,1,""],StartTLSCommand:[12,1,1,""]},"pymap.parsing.command.nonauth.AuthenticateCommand":{parse:[12,3,1,""]},"pymap.parsing.command.nonauth.LoginCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select":{CheckCommand:[12,1,1,""],CloseCommand:[12,1,1,""],CopyCommand:[12,1,1,""],ExpungeCommand:[12,1,1,""],FetchCommand:[12,1,1,""],IdleCommand:[12,1,1,""],SearchCommand:[12,1,1,""],StoreCommand:[12,1,1,""],UidCommand:[12,1,1,""],UidCopyCommand:[12,1,1,""],UidExpungeCommand:[12,1,1,""],UidFetchCommand:[12,1,1,""],UidSearchCommand:[12,1,1,""],UidStoreCommand:[12,1,1,""]},"pymap.parsing.command.select.CopyCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.ExpungeCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.FetchCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.IdleCommand":{continuation:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.select.SearchCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.StoreCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.UidCommand":{parse:[12,3,1,""]},"pymap.parsing.command.select.UidCopyCommand":{delegate:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.select.UidExpungeCommand":{delegate:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.select.UidFetchCommand":{delegate:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.select.UidSearchCommand":{delegate:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.command.select.UidStoreCommand":{delegate:[12,4,1,""],parse:[12,3,1,""]},"pymap.parsing.commands":{Commands:[12,1,1,""]},"pymap.parsing.commands.Commands":{parse:[12,2,1,""]},"pymap.parsing.exceptions":{BadCommand:[12,5,1,""],CommandInvalid:[12,5,1,""],CommandNotFound:[12,5,1,""],InvalidContent:[12,5,1,""],NotParseable:[12,5,1,""],RequiresContinuation:[12,5,1,""],UnexpectedType:[12,5,1,""]},"pymap.parsing.exceptions.BadCommand":{code:[12,4,1,""],get_response:[12,2,1,""]},"pymap.parsing.exceptions.CommandInvalid":{cause:[12,4,1,""],code:[12,4,1,""]},"pymap.parsing.exceptions.NotParseable":{after:[12,4,1,""],before:[12,4,1,""]},"pymap.parsing.primitives":{Atom:[12,1,1,""],ListP:[12,1,1,""],LiteralString:[12,1,1,""],Nil:[12,1,1,""],Number:[12,1,1,""],QuotedString:[12,1,1,""],String:[12,1,1,""]},"pymap.parsing.primitives.Atom":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.primitives.ListP":{get_as:[12,2,1,""],parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.primitives.LiteralString":{parse:[12,3,1,""]},"pymap.parsing.primitives.Nil":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.primitives.Number":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.primitives.QuotedString":{parse:[12,3,1,""]},"pymap.parsing.primitives.String":{binary:[12,4,1,""],build:[12,3,1,""],parse:[12,3,1,""],string:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.response":{Response:[12,1,1,""],ResponseBad:[12,1,1,""],ResponseBye:[12,1,1,""],ResponseCode:[12,1,1,""],ResponseContinuation:[12,1,1,""],ResponseNo:[12,1,1,""],ResponseOk:[12,1,1,""],ResponsePreAuth:[12,1,1,""],code:[12,0,0,"-"],fetch:[12,0,0,"-"],specials:[12,0,0,"-"]},"pymap.parsing.response.Response":{add_untagged:[12,2,1,""],add_untagged_ok:[12,2,1,""],condition:[12,4,1,""],is_terminal:[12,4,1,""],merge:[12,2,1,""],merge_key:[12,4,1,""],tag:[12,4,1,""],text:[12,4,1,""]},"pymap.parsing.response.ResponseBye":{is_terminal:[12,4,1,""]},"pymap.parsing.response.ResponseCode":{of:[12,3,1,""]},"pymap.parsing.response.code":{Alert:[12,1,1,""],AppendUid:[12,1,1,""],Capability:[12,1,1,""],CopyUid:[12,1,1,""],Parse:[12,1,1,""],PermanentFlags:[12,1,1,""],ReadOnly:[12,1,1,""],ReadWrite:[12,1,1,""],TryCreate:[12,1,1,""],UidNext:[12,1,1,""],UidValidity:[12,1,1,""],Unseen:[12,1,1,""]},"pymap.parsing.response.code.Capability":{string:[12,4,1,""]},"pymap.parsing.response.fetch":{BodyStructure:[12,1,1,""],ContentBodyStructure:[12,1,1,""],EnvelopeStructure:[12,1,1,""],MessageBodyStructure:[12,1,1,""],MultipartBodyStructure:[12,1,1,""],TextBodyStructure:[12,1,1,""]},"pymap.parsing.response.fetch.BodyStructure":{extended:[12,4,1,""]},"pymap.parsing.response.fetch.ContentBodyStructure":{extended:[12,4,1,""]},"pymap.parsing.response.fetch.MessageBodyStructure":{extended:[12,4,1,""]},"pymap.parsing.response.fetch.MultipartBodyStructure":{extended:[12,4,1,""]},"pymap.parsing.response.fetch.TextBodyStructure":{extended:[12,4,1,""]},"pymap.parsing.response.specials":{ESearchResponse:[12,1,1,""],ExistsResponse:[12,1,1,""],ExpungeResponse:[12,1,1,""],FetchResponse:[12,1,1,""],FlagsResponse:[12,1,1,""],LSubResponse:[12,1,1,""],ListResponse:[12,1,1,""],RecentResponse:[12,1,1,""],SearchResponse:[12,1,1,""],StatusResponse:[12,1,1,""]},"pymap.parsing.response.specials.ESearchResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.ExistsResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.ExpungeResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.FetchResponse":{merge:[12,2,1,""],merge_key:[12,4,1,""],text:[12,4,1,""]},"pymap.parsing.response.specials.FlagsResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.ListResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.RecentResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.SearchResponse":{text:[12,4,1,""]},"pymap.parsing.response.specials.StatusResponse":{text:[12,4,1,""]},"pymap.parsing.specials":{astring:[12,0,0,"-"],datetime_:[12,0,0,"-"],fetchattr:[12,0,0,"-"],flag:[12,0,0,"-"],mailbox:[12,0,0,"-"],options:[12,0,0,"-"],searchkey:[12,0,0,"-"],sequenceset:[12,0,0,"-"],statusattr:[12,0,0,"-"],tag:[12,0,0,"-"]},"pymap.parsing.specials.astring":{AString:[12,1,1,""]},"pymap.parsing.specials.astring.AString":{parse:[12,3,1,""],string:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.specials.datetime_":{DateTime:[12,1,1,""]},"pymap.parsing.specials.datetime_.DateTime":{get_local_tzinfo:[12,3,1,""],parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.fetchattr":{FetchAttribute:[12,1,1,""]},"pymap.parsing.specials.fetchattr.FetchAttribute":{Section:[12,1,1,""],parse:[12,3,1,""],partial:[12,4,1,""],section:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.specials.fetchattr.FetchAttribute.Section":{headers:[12,4,1,""],parts:[12,4,1,""],specifier:[12,4,1,""]},"pymap.parsing.specials.flag":{Answered:[12,7,1,""],Deleted:[12,7,1,""],Draft:[12,7,1,""],Flag:[12,1,1,""],Flagged:[12,7,1,""],Recent:[12,7,1,""],Seen:[12,7,1,""],get_system_flags:[12,6,1,""]},"pymap.parsing.specials.flag.Flag":{is_system:[12,4,1,""],parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.mailbox":{Mailbox:[12,1,1,""]},"pymap.parsing.specials.mailbox.Mailbox":{decode_name:[12,3,1,""],encode_name:[12,3,1,""],parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.options":{ExtensionOption:[12,1,1,""],ExtensionOptions:[12,1,1,""]},"pymap.parsing.specials.options.ExtensionOption":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.options.ExtensionOptions":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.searchkey":{SearchKey:[12,1,1,""]},"pymap.parsing.specials.searchkey.SearchKey":{not_inverse:[12,4,1,""],parse:[12,3,1,""],value:[12,4,1,""]},"pymap.parsing.specials.sequenceset":{SequenceSet:[12,1,1,""]},"pymap.parsing.specials.sequenceset.SequenceSet":{all:[12,3,1,""],build:[12,3,1,""],contains:[12,2,1,""],iter:[12,2,1,""],parse:[12,3,1,""],uid:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.specials.statusattr":{StatusAttribute:[12,1,1,""]},"pymap.parsing.specials.statusattr.StatusAttribute":{parse:[12,3,1,""],valid_statuses:[12,4,1,""],value:[12,4,1,""]},"pymap.parsing.specials.tag":{Tag:[12,1,1,""]},"pymap.parsing.specials.tag.Tag":{parse:[12,3,1,""],value:[12,4,1,""]},"pymap.proxy":{ExecutorProxy:[13,1,1,""]},"pymap.proxy.ExecutorProxy":{wrap_login:[13,2,1,""],wrap_session:[13,2,1,""]},"pymap.search":{AllSearchCriteria:[14,1,1,""],BodySearchCriteria:[14,1,1,""],DateSearchCriteria:[14,1,1,""],EnvelopeSearchCriteria:[14,1,1,""],HasFlagSearchCriteria:[14,1,1,""],HeaderDateSearchCriteria:[14,1,1,""],HeaderSearchCriteria:[14,1,1,""],InverseSearchCriteria:[14,1,1,""],NewSearchCriteria:[14,1,1,""],OrSearchCriteria:[14,1,1,""],SearchCriteria:[14,1,1,""],SearchCriteriaSet:[14,1,1,""],SearchParams:[14,1,1,""],SequenceSetSearchCriteria:[14,1,1,""],SizeSearchCriteria:[14,1,1,""]},"pymap.search.AllSearchCriteria":{matches:[14,2,1,""]},"pymap.search.BodySearchCriteria":{matches:[14,2,1,""]},"pymap.search.DateSearchCriteria":{matches:[14,2,1,""]},"pymap.search.EnvelopeSearchCriteria":{matches:[14,2,1,""]},"pymap.search.HasFlagSearchCriteria":{matches:[14,2,1,""]},"pymap.search.HeaderSearchCriteria":{matches:[14,2,1,""]},"pymap.search.InverseSearchCriteria":{matches:[14,2,1,""]},"pymap.search.NewSearchCriteria":{matches:[14,2,1,""]},"pymap.search.OrSearchCriteria":{matches:[14,2,1,""]},"pymap.search.SearchCriteria":{matches:[14,2,1,""],of:[14,3,1,""]},"pymap.search.SearchCriteriaSet":{matches:[14,2,1,""]},"pymap.search.SequenceSetSearchCriteria":{matches:[14,2,1,""]},"pymap.search.SizeSearchCriteria":{matches:[14,2,1,""]},"pymap.selected":{SelectedMailbox:[15,1,1,""],SelectedSet:[15,1,1,""],SelectedSnapshot:[15,1,1,""]},"pymap.selected.SelectedMailbox":{add_messages:[15,2,1,""],exists:[15,4,1,""],fork:[15,2,1,""],hide:[15,2,1,""],hide_expunged:[15,2,1,""],kwargs:[15,4,1,""],max_uid:[15,4,1,""],name:[15,4,1,""],readonly:[15,4,1,""],recent:[15,4,1,""],remove_messages:[15,2,1,""],session_flags:[15,4,1,""],set_deleted:[15,2,1,""],set_uid_validity:[15,2,1,""],snapshot:[15,4,1,""],uid_validity:[15,4,1,""]},"pymap.selected.SelectedSet":{any_selected:[15,4,1,""],updated:[15,4,1,""]},"pymap.selected.SelectedSnapshot":{exists:[15,4,1,""],iter_set:[15,2,1,""],max_uid:[15,4,1,""],messages:[15,4,1,""],recent:[15,4,1,""],uid_validity:[15,4,1,""]},"pymap.server":{IMAPConnection:[16,1,1,""],IMAPServer:[16,1,1,""]},"pymap.server.IMAPConnection":{run:[16,2,1,""]},"pymap.sockinfo":{SocketInfo:[17,1,1,""]},"pymap.state":{ConnectionState:[18,1,1,""]},pymap:{concurrent:[1,0,0,"-"],config:[2,0,0,"-"],exceptions:[3,0,0,"-"],flags:[4,0,0,"-"],listtree:[9,0,0,"-"],mailbox:[10,0,0,"-"],message:[11,0,0,"-"],parsing:[12,0,0,"-"],proxy:[13,0,0,"-"],search:[14,0,0,"-"],selected:[15,0,0,"-"],server:[16,0,0,"-"],sockinfo:[17,0,0,"-"],state:[18,0,0,"-"]}},objnames:{"0":["py","module","Python module"],"1":["py","class","Python class"],"2":["py","method","Python method"],"3":["py","classmethod","Python class method"],"4":["py","attribute","Python attribute"],"5":["py","exception","Python exception"],"6":["py","function","Python function"],"7":["py","data","Python data"]},objtypes:{"0":"py:module","1":"py:class","2":"py:method","3":"py:classmethod","4":"py:attribute","5":"py:exception","6":"py:function","7":"py:data"},terms:{"2nd":[5,11],"3rd":[5,11],"byte":[3,5,6,8,9,10,11,12,14],"case":[4,8,12,17],"catch":12,"class":[1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18],"default":[7,8,15],"enum":4,"float":1,"function":[10,13],"import":8,"int":[2,4,5,6,8,10,11,12,14,15],"new":[1,2,5,6,7,8,10,11,12,14,15,16],"return":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],"static":10,"true":[1,2,5,6,10,11,12],"while":[4,12],For:[5,11,12],NOT:12,TLS:[2,12],The:[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],Then:15,These:12,Used:[4,7,8],Uses:1,With:8,__call__:5,_asyncenumer:6,_base:1,_baselayout:8,_configt:[2,5],_elementt:6,_eventt:1,_loadedsearchcriteria:14,_loadedt:11,_messaget:[5,11],_parseablet:12,_responset:12,_selectedt:[5,15],_sessiont:[7,8],abil:12,about:[5,12,15,17],absenc:1,absent:1,absolut:8,abstractasynccontextmanag:1,accept:16,access:17,acquir:1,across:15,activ:[2,14],actual:12,add:[4,8,9,12,15],add_fold:8,add_messag:15,add_rec:4,add_untag:12,add_untagged_ok:12,added:[4,5,9,11,15],adding:12,addit:[1,2,5,6,7,8],addition:12,addresshead:12,adjac:8,adjust:15,advertis:12,after:[3,5,6,12],after_nam:[5,6],again:1,against:14,age:1,alert:12,alia:[8,9,11,12,15],all:[1,2,3,4,5,6,8,9,10,12,13,14,15],allow:[1,2,3,5,10,12],allsearchcriteria:14,along:12,alreadi:[5,6,8,12],also:15,altern:2,alwai:[12,14],among:12,ani:[1,2,4,5,6,7,8,9,12,14,15],anonym:12,anoth:[1,3],answer:12,any_select:15,anyth:14,append:[2,3,5,6,11,12],append_messag:[5,6],appendcommand:12,appendfailur:[3,5,6],appendmessag:[5,6,11],appenduid:[5,6,12],applic:[5,6],arg:[2,5,6,7,8,11,12],argument:[1,2,5,6,7,8,10,11,12,15],around:12,assign:[8,11,12,15],associ:12,asterisk:12,astr:12,async:6,asyncenumer:6,asyncio:[1,15,16],asynciter:[1,6],atom:12,attempt:[1,12],attent:12,attr:[9,12],attr_list:12,attribut:[5,6,9,11,12,17],auth:12,authent:[2,3,5,12,16,17],authenticatecommand:12,authenticationcredenti:[2,5],author:17,avail:[5,8,10,12,16],back:12,backend:[2,3,5,6,7,8,10,12,15,16,18],bad:12,bad_command_limit:2,badcommand:12,base:[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18],base_dir:8,baseloadedmessag:[6,11],basemessag:11,basic:[12,16],bcc:12,becaus:[3,12],been:[12,15],befor:[1,2,5,6,12],before_nam:[5,6],begin:12,being:12,below:3,between:[1,7],binari:[5,11,12],bit:[5,8,11],block:[1,5,6],bodi:[2,5,11,12,14],body_md5:12,body_structur:12,bodysearchcriteria:14,bodystructur:[5,11,12],bool:[1,2,3,5,6,7,10,11,12,14,15],bound:12,bracket:12,buf:12,buffer:12,build:[2,3,5,11,12],bye:12,bytestr:[11,12],call:[1,13,15],callabl:16,callback:[5,16],came:12,can:[2,5,10,11,12,18],cannot:3,capabilitycommand:12,capabl:[2,12],carriag:12,carriage_return:12,caus:12,cert_fil:2,certain:14,chang:[5,11,12,15],charact:[8,12],character:12,charset:12,check:[5,6,7,8,12,14,17],check_mailbox:[5,6],checkcommand:12,child:[5,6],chosen:15,circumst:2,classmethod:[1,2,7,8,10,11,12,14],clear:[1,12],cleartext:2,client:[2,4,12],close:[3,12],closecommand:12,closeconnect:3,cls:12,cmp:14,code:[3,8,12],colon:8,come:12,command:[0,2,3,7,8,11,15,16,18],command_nam:12,commandani:12,commandauth:12,commandinvalid:12,commandmailboxarg:12,commandnoarg:12,commandnonauth:12,commandnotallow:3,commandnotfound:12,commandselect:12,commun:16,compar:[12,14,15],complet:[12,15],compos:14,compound:12,concurr:[0,7,12,15],condit:12,config:[0,5,7,8,16,18],configur:[2,7,8],conflict:3,connect:[2,3,4,5,12,16,17,18],connectionst:[16,18],consecut:2,consid:14,consist:10,construct:[9,12,15],constructor:[2,7,8,10],contain:[3,8,11,12,14],content:[5,6,7,8,11,12],content_descript:12,content_disposit:12,content_id:12,content_languag:12,content_loc:12,content_transfer_encod:12,content_type_param:12,contentbodystructur:12,contentdispositionhead:12,context:2,continu:12,control:[2,12],conveni:[4,12],convert:[5,15],copi:[5,6,11,12,15],copy_messag:[5,6],copycommand:12,copyuid:[5,6,12],correct:12,correspond:[5,6,8],could:[3,5,6],count:4,count_rec:4,creat:[1,2,3,5,6,10,12,16],create_mailbox:[5,6],createcommand:12,credenti:[2,3,5,7,8,12,16],criteria:[5,6,12,14],crlf:12,current:[1,4,5,6,8,11,12,15],custom:[3,7,8],cycl:16,data:[7,11,12],date:[5,11,12,14],datehead:12,datesearchcriteria:14,datetim:[5,11,12],datetime_:12,deadlin:1,debug:2,decod:12,decode_nam:12,decor:17,defaultlayout:8,defin:[4,5,7,8,10,12,14,16,18],delai:1,deleg:12,delet:[1,3,4,5,6,12,15],delete_mailbox:[5,6],deletecommand:12,delimit:[6,7,8,9],demo:7,demo_data:7,demo_password:7,demo_us:7,demopass:7,demous:7,depth:12,deriv:12,describ:5,descript:12,desir:12,dest_nam:8,destin:[5,6,8,12],detect:[5,6],determin:18,dict:[0,6,12],dictionari:[2,7,8,12],did:[8,12],differ:[12,14],directli:[12,17],directori:8,disabl:[2,14],disable_idl:2,disconnect:[2,12],disk:8,displai:3,disposit:12,doe:[5,6,8,12,14],done:12,doubl:12,dovecot:8,draft:12,durat:1,dure:[12,15],each:[1,8,12,15],either:[1,12,14],email:11,emailmessag:11,empti:[8,12,14],encas:12,enclos:12,encod:[5,11,12],encode_nam:12,encoded_mailbox:12,encount:12,encrypt:[2,12],end:[5,6,12],endlin:12,enotempti:8,enter:16,entir:10,entri:[9,12],enumer:6,envelop:[5,11,12,14],envelope_structur:12,envelopesearchcriteria:14,envelopestructur:[5,11,12],eras:12,error:[1,2,3,12],esearch:12,esearchrespons:12,establish:1,etc:8,event:[1,5,6,15],everi:[10,12],examin:12,examinecommand:12,exampl:[5,7,11,12],exceed:1,except:[0,1,5,6],exclus:12,execut:[3,12],executor:[2,13],executorproxi:13,exhaust:1,exist:[4,5,6,7,8,9,10,12,15],existsrespons:12,expect:[7,8,12,14],expectedpars:12,expir:1,expung:[5,6,12,15],expunge_mailbox:[5,6],expungecommand:12,expungerespons:12,extend:12,extens:[2,11,12],extensionopt:12,extra:[2,7,8],factori:14,fail:[3,12,14],fals:[2,3,5,6,9,11,12],far:12,fetch:[5,6,11,12,15],fetch_messag:[5,6],fetchattr:12,fetchattribut:[5,6,12],fetchcommand:12,fetchrespons:12,few:12,field:[8,9,11,14,15],file:[1,8],file_nam:8,fileexistserror:8,filelock:1,filenam:8,filenotfounderror:8,fileread:8,filesystem:[1,8],filesystemlayout:8,filewrit:8,fill:9,filter:[5,6,9,12],filter_:[5,6,9,12],find_us:8,finish:[12,15,16],first:[5,8,10,12],first_unseen:[5,10],fit:12,flag:[0,5,6,10,11,12,14,15],flag_op:[5,11],flag_set:[4,5,6,11],flagop:[4,5,6,11,12],flagsrespons:12,flip:12,flow:[16,18],folder:[5,6,8],follow:12,for_asyncio:1,for_thread:1,fork:15,form:12,formal:12,format:[8,12],found:[3,12],fresh:15,from:[2,4,5,6,7,8,11,12,14,15,16],from_:12,from_arg:2,from_mailbox:12,from_maildir:8,frozenset:[4,5,6,8,10,11,12,14,15],full:[5,10,11],futur:[1,7],gather:[5,11],gener:[3,10,12,15],get:[4,5,6,8,11],get_a:12,get_bodi:[5,11],get_body_structur:[5,11],get_envelope_structur:[5,11],get_extra_info:17,get_flag:[5,11],get_fold:8,get_head:[5,11],get_local_tzinfo:12,get_mailbox:[5,6],get_password:7,get_path:8,get_respons:[3,12],get_siz:[5,11],get_system_flag:12,get_text:[5,11],given:[1,2,4,5,6,7,8,9,11,12,14,15],global:8,global_uid:8,gone:1,greet:[12,16],group:12,had:12,handl:[12,16],handshak:12,has:[1,3,4,5,6,8,9,12,14],has_children:9,haschildren:9,hasflagsearchcriteria:14,hash:12,hashabl:12,hasnochildren:9,have:[5,6,12,15],header:[5,11,12,14],headerdatesearchcriteria:14,headersearchcriteria:14,heirarchi:[8,9,12],hidden:15,hide:15,hide_expung:15,hierarch:[3,9],hierarchi:8,highest:[14,15],hint:17,hold:15,hous:[5,6],housekeep:[5,6],how:[2,12],identifi:[5,11,12],idl:[2,12],idlecommand:12,imap:[2,3,4,5,8,12,14,16,18],imapconfig:[2,7,8,16],imapconnect:16,imapserv:16,imit:6,immedi:[3,5,6,12],implement:[1,5,6,7,8,10,11,12,14,15],improv:12,in_reply_to:12,inbox:[6,7,8],includ:[3,5,8,11,12],index:[0,5,6,11],indic:[8,12,15],inferior:3,inform:[5,11,12,17],inherit:12,initi:[5,12],input:16,insid:[2,13],instanti:12,instead:12,integ:12,integr:7,intend:12,interact:[12,16,18],interfac:[0,6,10,11],intern:[5,11,12,14],internal_d:[5,6,7,8,11],invalid:12,invalidauth:[3,7,8],invalidauthent:5,invalidcont:12,invers:[5,11,12],inversesearchcriteria:14,invert:[5,11,12],is_set:1,is_system:12,is_termin:12,issu:12,issuer_tag:12,item:12,iter:[4,5,6,8,9,10,11,12,14,15],iter_set:15,its:[5,7,8,11,12,13],junk:8,just:12,keep:[5,6],kei:[3,5,6,12,14],kept:15,keval:[0,6],key_fil:2,keyerror:8,keyval:[0,7,8],keyvalmailbox:[6,7,8],keyvalmessag:[6,7,8],keyvalsess:[6,7,8],keyword:[2,7,8,12,15],kind:14,known:12,kwarg:[5,6,7,8,11,15],languag:12,last:15,layout:6,least:12,left:14,length:[2,12],letter:8,lifetim:7,like:[8,12],line:[2,7,8,12],list:[5,6,8,9,11,12],list_expect:12,list_fold:8,list_mailbox:[5,6],list_match:9,listcommand:12,listentri:9,listp:12,listrespons:12,listtre:0,liter:12,literal_length:12,literalstr:12,load:[5,6,7,11],loadedmessag:[5,11],locat:12,lock:[1,8],lock_fil:8,log:12,logic:[7,8,17],login:[3,7,8,12,13,16,18],logincommand:12,loginprotocol:[5,13,16],logout:12,logoutcommand:12,longer:[5,6],look:8,lower:8,lsub:12,lsubcommand:12,lsubrespons:12,made:12,mai:[3,5,6,8,12,14,17],mailbox:[0,3,4,7,8,9,11,12,14,15],mailbox_delimit:8,mailboxconflict:[3,5,6],mailboxerror:3,mailboxformat:8,mailboxhaschildren:[3,5,6],mailboxinterfac:[5,6,10],mailboxnotfound:[3,5,6],mailboxreadonli:[3,5,6],mailboxsnapshot:[6,10],maildir:[0,6],maildir_flag:8,maildirflag:8,maildirlayout:8,main:12,maintain:[8,15],maintyp:12,make:15,manag:[8,14,15],map:[2,7,8,12,15],mark:[5,6,9,15],match:[9,14],max_append_len:[2,12],max_seq:14,max_uid:[14,15],max_valu:12,maximum:[2,12],maybebytest:12,md5:12,mech_nam:12,mechan:[2,12],meet:[5,6,12],memori:7,merg:12,merge_kei:12,mergeabl:12,messag:[0,2,3,4,6,7,8,10,12,14,15],message_id:12,messagebodystructur:12,metadata:[5,8,11],method:[2,5,6,7,8,12,13,14],might:8,mime:[11,12],misc:8,miss:9,mode:[5,6,11,12],modifi:12,modul:[0,3],more:12,most:12,msg:14,msg_seq:14,multipart:12,multipartbodystructur:12,must:[12,14],mutual:12,name:[3,5,6,7,8,9,10,11,12,14,15],namespac:[2,7,8],necessari:[5,6,11,12,14],need:[2,5,7,8,11,12],nest:[5,8,9,11,12],new_uid:[5,11],new_uid_valid:10,newli:12,newlin:12,newsearchcriteria:14,next:[5,8,10,12,15],next_:12,next_uid:[5,8,10],nil:12,node:9,non:[2,8,12],nonauth:12,none:[1,2,3,4,5,6,8,11,12,13,14,15,16],nonjunk:8,noop:12,noopcommand:12,noselect:9,not_invers:12,noth:[12,14],notifi:15,notpars:12,num:12,number:[2,4,5,8,9,10,11,12,15],object:[1,2,4,5,6,7,8,9,11,12,13,14,15,16,17,18],occur:[12,15],octet:[5,11],older:1,one:[1,12],onli:[3,4,5,6,7,10,12,14,15],only_subscrib:12,open:[3,12],oper:[1,2,3,4,5,6,11,12,15],operand:12,opportunist:[2,12],option:[1,2,3,5,6,8,10,11,12,13,14,15],or_ev:1,origin:12,orsearchcriteria:14,oserror:8,other:[1,3,5,6,12,15],output:16,over:6,overrid:[2,7,8],own:[5,6],packag:12,page:0,pair:12,param:[12,14],paramet:[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],parent:[3,8,12],pars:[0,2,7,8,11],parse_arg:[2,7,8],parse_don:12,parseabl:12,part:[5,8,9,11,12],partial:12,pass:[2,7,8,12,17],password:[7,8,12],path:[1,8],perform:[5,6],perman:[5,8,10,11,12,14,15],permanent_flag:[5,6,7,8,10,11],permanentflag:12,persist:4,place:12,plu:12,plugin:[16,18],point:18,pool:[2,13],portion:12,posit:8,possibl:[5,6,9,12],pre:2,preauth:12,preauth_credenti:2,preced:12,preceding_spac:12,predict:[5,10],prefix:12,presenc:1,present:[1,12],primari:12,primit:[0,1,15],print:2,process:[7,14,18],produc:[12,14,15],protocol:[5,6,8,12],provid:[1,3],proxi:0,pull:[5,11],python:6,queri:[9,12],quot:12,quotedstr:12,rais:[3,5,6,7,8,12],random:[10,15],rang:12,raw:[11,12],read:[1,3,5,6,8,10,12,15],read_lock:1,read_retry_delai:1,readabl:12,reader:16,readi:15,readonli:[5,6,10,12,15],readwrit:12,readwritelock:1,reason:12,rec:8,receiv:[2,3,12,16],recent:[4,5,6,7,8,10,12,14,15],recentrespons:12,recogn:8,record:8,ref_nam:[5,6,9,12],refer:[5,6,9,12],reflect:15,reject:[2,3],reject_insecure_auth:2,rel:8,relat:[3,12],releas:1,remain:12,remov:[1,4,5,6,8,15],remove_fold:8,remove_messag:15,renam:[3,5,6,8,12],rename_fold:8,rename_mailbox:[5,6],renamecommand:12,replac:[4,5,6,11,12],repli:12,reply_to:12,repres:12,request:[3,12],requir:[10,12,14],requirescontinu:12,respond:12,respons:[0,3,5,9,11,15,16],responsebad:12,responseby:12,responsecod:[3,12],responsecontinu:12,responseerror:3,responseno:[3,12],responseok:[3,12],responsepreauth:12,result:[4,5,9,11],retriev:[5,6,7,8],rfc822:12,rfc:[4,5,6,9,11,12],right:14,root:8,routin:14,run:[2,16],same:12,sasl:12,search:[0,3,5,6,12],search_mailbox:[5,6],searchcommand:12,searchcriteria:14,searchcriteriaset:14,searchkei:[5,6,12,14],searchnotallow:3,searchparam:14,searchrespons:12,second:[1,10],section:[5,11,12],see:[8,12],seen:12,select:[0,4,5,6,12,14],select_mailbox:[5,6],selectcommand:12,selected_set:15,selectedmailbox:[6,14,15],selectedset:15,selectedsnapshot:15,self:15,send:[3,12],sender:12,sent:12,sep:12,separ:12,seq:12,seq_set:[12,14,15],sequenc:[1,5,6,8,9,10,11,12,14,15],sequence_set:[5,6],sequenceset:[5,6,12,15],sequencesetsearchcriteria:14,serial:12,server:[0,2,5,12,17],server_cap:12,session:[0,4,7,8,10,11,12,13,14,15],session_flag:[5,10,11,15],sessionflag:[4,5,11,15],sessioninterfac:[5,6,13,16],set:[1,2,4,5,6,8,10,11,12,14,15,16],set_delet:15,set_uid_valid:15,share:7,shortcut:15,should:[2,3,4,5,6,7,8,9,12,14,15],shown:12,side:17,signal:[1,5,6],silent:12,simul:1,singl:[5,8,11,12,15,16],size:[5,11,12,14],sizesearchcriteria:14,sleep:1,slower:[5,6],snapshot:[10,15],sock_info:[5,7,8],socket:[2,5,16,17],socketinfo:[5,17],sockinfo:0,some:[1,12,14,17],someth:12,sooner:[5,6],sort:12,sourc:[8,12],source_nam:8,space:12,special:[0,2,4],specif:12,specifi:[5,6,12],split:8,squar:12,ssl:2,ssl_context:2,sslcontext:2,stage:12,standard:8,start:[6,8,16],start_serv:16,starttl:12,starttls_en:2,starttlscommand:12,state:[0,12,15,16],statu:[8,12],status_list:12,statusattr:12,statusattribut:12,statuscommand:12,statusrespons:12,stdout:2,storag:8,store:[8,12],storecommand:12,str:[1,2,3,5,6,7,8,9,10,12,15],stream:[12,16],streamread:16,streamwrit:16,string:[5,8,9,12,14],structur:[5,8,11,12,14],sub:[1,2,5,7,8,11,12,14],subject:12,subscrib:[5,6,8,12],subscribecommand:12,subscript:[5,6],subsequ:15,subset:[5,11,12],subsystem:1,subtyp:12,succe:12,success:1,successfulli:12,superior:9,suppli:[5,14],support:[2,8],supportsbyt:12,synchron:12,syntact:3,syntax:12,system:[1,5,8,11,12],system_flag:8,t_co:12,tag:[3,12],take:[12,16],termin:12,test:7,text:[5,11,12],textbodystructur:12,than:1,thei:[4,5,6,9,15],them:12,thi:[1,2,5,6,7,8,11,12,15],thread:[1,2,13],three:8,through:[8,12,13,15],thrown:1,time:[10,12],timeout:[1,12],timeouterror:1,timestamp:[11,12],timezon:12,to_mailbox:12,to_maildir:8,top:8,total:[5,10,15],track:4,transfer:12,transmit:[2,12],transport:[2,17],trash:8,travers:8,tree:9,try_creat:3,trycreat:[3,12],tupl:[5,6,8,9,11,12,15],two:[10,12],type:[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17],typeerror:12,typic:12,typing_extens:[5,6,8],tzinfo:12,uid:[4,5,6,7,8,10,11,12,14,15],uid_set:[5,6,12],uid_valid:[5,8,10,15],uidcommand:12,uidcopycommand:12,uidexpungecommand:12,uidfetchcommand:12,uidlist:6,uidnext:12,uidsearchcommand:12,uidstorecommand:12,uidvalid:12,unexpectedtyp:12,union:[8,12],uniqu:[5,11,12],unless:12,unquot:12,unreferenc:9,unseen:[5,10,12,14],unsolicit:12,unstructuredhead:12,unsubscrib:[5,6,12],unsubscribecommand:12,untag:[12,15],until:[1,5,6,12,15],updat:[4,5,6,8,9,11,12,15],update_flag:[5,6,11],usag:7,use:[5,8,11,12,16],used:[1,2,3,5,6,7,8,12,14],useful:[12,15,17],user:[5,6,7,8,12],userid:12,users_fil:8,uses:[5,7,8,11,12],using:[1,2,8,10,12,15],utf:12,util:[0,1,14],valid:[3,4,5,7,8,10,12,15],valid_status:12,valu:[4,5,6,8,10,11,12,14,15],valueerror:[8,12],variant:12,variou:14,wai:12,wait:[1,12],wait_on:[5,6],weak:15,well:15,what:[2,12],when:[1,3,4,5,11,12,14,15,16],where:10,whether:[3,5,6,9,10,12],which:[5,6,7,8,12,17],wildcard:[5,6,9],with_head:14,within:[12,14],without:12,work:4,would:[5,11,12],wrap:13,wrap_login:13,wrap_sess:13,write:[1,5,10,12],write_lock:1,write_retry_delai:1,writer:16,written:15,yet:[5,6,12],you:2,zero:12},titles:["<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap</span></code> Documentation","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.concurrent</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.config</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.exceptions</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.flags</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.interfaces</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.keyval</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.keval.dict</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.keval.maildir</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.listtree</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.mailbox</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.message</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.parsing</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.proxy</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.search</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.selected</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.server</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.sockinfo</span></code>","<code class=\"docutils literal notranslate\"><span class=\"pre\">pymap.state</span></code>"],titleterms:{command:12,concurr:1,config:2,content:0,dict:7,document:0,except:[3,12],flag:[4,8],indic:0,interfac:5,keval:[7,8],keyval:6,layout:8,listtre:9,mailbox:[5,6,10],maildir:8,messag:[5,11],pars:12,primit:12,proxi:13,pymap:[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18],respons:12,search:14,select:15,server:16,session:[5,6],sockinfo:17,special:12,state:18,subscript:8,tabl:0,uidlist:8,util:6}})