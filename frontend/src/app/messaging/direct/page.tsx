"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Mail,
  Send,
  Inbox,
  Archive,
  Trash2,
  Search,
  Plus,
  Paperclip,
  Shield,
  CheckCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Settings,
  Users,
  Building,
  Lock,
  FileText,
  Download,
  Reply,
  Forward,
  Star,
} from "lucide-react";

// Types
interface DirectMessage {
  id: string;
  from: string;
  fromOrg: string;
  to: string;
  toOrg: string;
  subject: string;
  body: string;
  status: "sent" | "delivered" | "read" | "failed" | "draft";
  hasAttachments: boolean;
  attachmentCount?: number;
  timestamp: string;
  encrypted: boolean;
  starred: boolean;
  folder: "inbox" | "sent" | "drafts" | "archive" | "trash";
}

interface DirectAddress {
  id: string;
  address: string;
  name: string;
  organization: string;
  type: "provider" | "organization" | "patient";
  verified: boolean;
  lastContact?: string;
}

interface TrustBundle {
  id: string;
  name: string;
  type: "DirectTrust" | "HISP" | "Custom";
  status: "active" | "inactive";
  certCount: number;
  lastUpdated: string;
}

// Mock data
const mockMessages: DirectMessage[] = [
  {
    id: "msg-1",
    from: "dr.smith@directtrust.org",
    fromOrg: "City General Hospital",
    to: "clinic@medicalpractice.direct.org",
    toOrg: "Medical Practice Group",
    subject: "Patient Referral - John Doe",
    body: "Please find attached the referral documents for patient John Doe. The patient requires a cardiology consultation for suspected atrial fibrillation...",
    status: "delivered",
    hasAttachments: true,
    attachmentCount: 3,
    timestamp: "2026-01-24T10:30:00Z",
    encrypted: true,
    starred: true,
    folder: "inbox",
  },
  {
    id: "msg-2",
    from: "lab@reference-lab.direct.org",
    fromOrg: "Reference Laboratory Inc",
    to: "clinic@medicalpractice.direct.org",
    toOrg: "Medical Practice Group",
    subject: "Lab Results - Patient ID: 12345",
    body: "The requested laboratory tests have been completed. Please review the attached results...",
    status: "read",
    hasAttachments: true,
    attachmentCount: 1,
    timestamp: "2026-01-24T09:15:00Z",
    encrypted: true,
    starred: false,
    folder: "inbox",
  },
  {
    id: "msg-3",
    from: "clinic@medicalpractice.direct.org",
    fromOrg: "Medical Practice Group",
    to: "discharge@hospital.direct.org",
    toOrg: "Regional Medical Center",
    subject: "Discharge Summary Request",
    body: "Requesting discharge summary for patient Mary Johnson who was seen at your facility on January 20th...",
    status: "sent",
    hasAttachments: false,
    timestamp: "2026-01-24T08:45:00Z",
    encrypted: true,
    starred: false,
    folder: "sent",
  },
  {
    id: "msg-4",
    from: "pharmacy@cvs.direct.org",
    fromOrg: "CVS Pharmacy",
    to: "clinic@medicalpractice.direct.org",
    toOrg: "Medical Practice Group",
    subject: "Prescription Renewal Request",
    body: "Patient requests renewal for Metformin 500mg. Current prescription expires in 5 days...",
    status: "delivered",
    hasAttachments: false,
    timestamp: "2026-01-24T07:30:00Z",
    encrypted: true,
    starred: false,
    folder: "inbox",
  },
  {
    id: "msg-5",
    from: "clinic@medicalpractice.direct.org",
    fromOrg: "Medical Practice Group",
    to: "specialist@cardiology.direct.org",
    toOrg: "Cardiology Associates",
    subject: "Follow-up Appointment Confirmation",
    body: "This is to confirm the follow-up appointment for patient Robert Brown on February 1st...",
    status: "failed",
    hasAttachments: false,
    timestamp: "2026-01-23T16:00:00Z",
    encrypted: true,
    starred: false,
    folder: "sent",
  },
];

const mockAddresses: DirectAddress[] = [
  { id: "addr-1", address: "dr.smith@directtrust.org", name: "Dr. Sarah Smith", organization: "City General Hospital", type: "provider", verified: true, lastContact: "2026-01-24T10:30:00Z" },
  { id: "addr-2", address: "lab@reference-lab.direct.org", name: "Reference Lab", organization: "Reference Laboratory Inc", type: "organization", verified: true, lastContact: "2026-01-24T09:15:00Z" },
  { id: "addr-3", address: "pharmacy@cvs.direct.org", name: "CVS Pharmacy", organization: "CVS Pharmacy", type: "organization", verified: true, lastContact: "2026-01-24T07:30:00Z" },
  { id: "addr-4", address: "specialist@cardiology.direct.org", name: "Dr. Michael Chen", organization: "Cardiology Associates", type: "provider", verified: true, lastContact: "2026-01-23T16:00:00Z" },
  { id: "addr-5", address: "discharge@hospital.direct.org", name: "Discharge Team", organization: "Regional Medical Center", type: "organization", verified: true, lastContact: "2026-01-24T08:45:00Z" },
];

const mockTrustBundles: TrustBundle[] = [
  { id: "tb-1", name: "DirectTrust Production", type: "DirectTrust", status: "active", certCount: 45230, lastUpdated: "2026-01-24T00:00:00Z" },
  { id: "tb-2", name: "State HIE Trust Bundle", type: "HISP", status: "active", certCount: 8920, lastUpdated: "2026-01-23T12:00:00Z" },
  { id: "tb-3", name: "Partner Organization Certs", type: "Custom", status: "active", certCount: 156, lastUpdated: "2026-01-22T15:30:00Z" },
];

export default function DirectMessagingPage() {
  const [messages] = useState<DirectMessage[]>(mockMessages);
  const [addresses] = useState<DirectAddress[]>(mockAddresses);
  const [trustBundles] = useState<TrustBundle[]>(mockTrustBundles);
  const [selectedFolder, setSelectedFolder] = useState<string>("inbox");
  const [selectedMessage, setSelectedMessage] = useState<DirectMessage | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [composeOpen, setComposeOpen] = useState(false);
  const [newMessage, setNewMessage] = useState({
    to: "",
    subject: "",
    body: "",
    attachCcd: false,
  });

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 24 * 60 * 60 * 1000) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "delivered":
      case "read":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "sent":
        return <Clock className="h-4 w-4 text-blue-500" />;
      case "failed":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const folderMessages = messages.filter(
    (m) =>
      m.folder === selectedFolder &&
      (searchQuery === "" ||
        m.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.from.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const inboxCount = messages.filter((m) => m.folder === "inbox" && m.status !== "read").length;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Direct Secure Messaging</h1>
          <p className="text-muted-foreground">
            HIPAA-compliant healthcare messaging using Direct Protocol
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
          <Dialog open={composeOpen} onOpenChange={setComposeOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Compose
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Compose Secure Message</DialogTitle>
                <DialogDescription>
                  Send encrypted messages to verified Direct addresses
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>To (Direct Address)</Label>
                  <Select
                    value={newMessage.to}
                    onValueChange={(v) => setNewMessage({ ...newMessage, to: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select recipient" />
                    </SelectTrigger>
                    <SelectContent>
                      {addresses.map((addr) => (
                        <SelectItem key={addr.id} value={addr.address}>
                          <div className="flex items-center gap-2">
                            {addr.verified && <Shield className="h-3 w-3 text-green-500" />}
                            <span>{addr.name}</span>
                            <span className="text-muted-foreground text-xs">
                              ({addr.address})
                            </span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Subject</Label>
                  <Input
                    value={newMessage.subject}
                    onChange={(e) => setNewMessage({ ...newMessage, subject: e.target.value })}
                    placeholder="Enter subject"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Message</Label>
                  <Textarea
                    value={newMessage.body}
                    onChange={(e) => setNewMessage({ ...newMessage, body: e.target.value })}
                    placeholder="Enter your message..."
                    rows={8}
                  />
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2">
                    <Switch
                      checked={newMessage.attachCcd}
                      onCheckedChange={(c) => setNewMessage({ ...newMessage, attachCcd: c })}
                    />
                    <span className="text-sm">Attach CCD Document</span>
                  </label>
                  <Button variant="outline" size="sm">
                    <Paperclip className="h-4 w-4 mr-2" />
                    Add Attachment
                  </Button>
                </div>

                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Lock className="h-4 w-4" />
                  <span>Message will be encrypted using S/MIME</span>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setComposeOpen(false)}>
                  Save Draft
                </Button>
                <Button onClick={() => setComposeOpen(false)}>
                  <Send className="h-4 w-4 mr-2" />
                  Send Message
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Inbox className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Inbox</p>
                <p className="text-2xl font-bold">
                  {messages.filter((m) => m.folder === "inbox").length}
                  {inboxCount > 0 && (
                    <Badge variant="destructive" className="ml-2">
                      {inboxCount} new
                    </Badge>
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Send className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Sent</p>
                <p className="text-2xl font-bold">
                  {messages.filter((m) => m.folder === "sent").length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Trust Bundles</p>
                <p className="text-2xl font-bold">
                  {trustBundles.filter((t) => t.status === "active").length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Contacts</p>
                <p className="text-2xl font-bold">{addresses.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Folders */}
        <Card className="col-span-1">
          <CardContent className="pt-6 space-y-2">
            <Button
              variant={selectedFolder === "inbox" ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelectedFolder("inbox")}
            >
              <Inbox className="h-4 w-4 mr-2" />
              Inbox
              {inboxCount > 0 && (
                <Badge variant="destructive" className="ml-auto">
                  {inboxCount}
                </Badge>
              )}
            </Button>
            <Button
              variant={selectedFolder === "sent" ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelectedFolder("sent")}
            >
              <Send className="h-4 w-4 mr-2" />
              Sent
            </Button>
            <Button
              variant={selectedFolder === "drafts" ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelectedFolder("drafts")}
            >
              <FileText className="h-4 w-4 mr-2" />
              Drafts
            </Button>
            <Button
              variant={selectedFolder === "archive" ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelectedFolder("archive")}
            >
              <Archive className="h-4 w-4 mr-2" />
              Archive
            </Button>
            <Button
              variant={selectedFolder === "trash" ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelectedFolder("trash")}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Trash
            </Button>
          </CardContent>
        </Card>

        {/* Message List */}
        <Card className="col-span-3">
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <CardTitle className="capitalize">{selectedFolder}</CardTitle>
              <div className="flex gap-2">
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search messages..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 w-[250px]"
                  />
                </div>
                <Button variant="outline" size="icon">
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {folderMessages.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No messages in this folder</p>
              </div>
            ) : (
              <ScrollArea className="h-[400px]">
                <div className="space-y-1">
                  {folderMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`p-3 rounded-lg cursor-pointer hover:bg-slate-50 border ${
                        selectedMessage?.id === message.id ? "bg-blue-50 border-blue-200" : "border-transparent"
                      } ${message.status !== "read" && selectedFolder === "inbox" ? "font-medium" : ""}`}
                      onClick={() => setSelectedMessage(message)}
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 mt-1">
                          {message.encrypted && (
                            <Lock className="h-4 w-4 text-green-500" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {message.starred && (
                                <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                              )}
                              <span className="truncate">
                                {selectedFolder === "sent" ? message.to : message.from}
                              </span>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(message.timestamp)}
                            </span>
                          </div>
                          <p className="text-sm truncate">{message.subject}</p>
                          <div className="flex items-center gap-2 mt-1">
                            {getStatusIcon(message.status)}
                            <span className="text-xs text-muted-foreground truncate">
                              {message.fromOrg}
                            </span>
                            {message.hasAttachments && (
                              <Badge variant="outline" className="text-xs">
                                <Paperclip className="h-3 w-3 mr-1" />
                                {message.attachmentCount}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Message Detail */}
      {selectedMessage && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle>{selectedMessage.subject}</CardTitle>
                <CardDescription className="mt-1">
                  <div className="flex items-center gap-2">
                    <Building className="h-4 w-4" />
                    <span>
                      {selectedFolder === "sent" ? selectedMessage.toOrg : selectedMessage.fromOrg}
                    </span>
                  </div>
                  <div className="text-xs mt-1">
                    From: {selectedMessage.from} •{" "}
                    To: {selectedMessage.to} •{" "}
                    {new Date(selectedMessage.timestamp).toLocaleString()}
                  </div>
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Reply className="h-4 w-4 mr-2" />
                  Reply
                </Button>
                <Button variant="outline" size="sm">
                  <Forward className="h-4 w-4 mr-2" />
                  Forward
                </Button>
                <Button variant="outline" size="sm">
                  <Archive className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="prose max-w-none">
              <p>{selectedMessage.body}</p>
            </div>

            {selectedMessage.hasAttachments && (
              <div className="mt-6 p-4 bg-slate-50 rounded-lg">
                <Label className="text-sm font-medium">
                  Attachments ({selectedMessage.attachmentCount})
                </Label>
                <div className="flex gap-2 mt-2">
                  {Array.from({ length: selectedMessage.attachmentCount || 0 }).map((_, i) => (
                    <Button key={i} variant="outline" size="sm">
                      <FileText className="h-4 w-4 mr-2" />
                      Document_{i + 1}.pdf
                      <Download className="h-4 w-4 ml-2" />
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Trust & Contacts Tabs */}
      <Tabs defaultValue="contacts">
        <TabsList>
          <TabsTrigger value="contacts">
            <Users className="h-4 w-4 mr-2" />
            Address Book
          </TabsTrigger>
          <TabsTrigger value="trust">
            <Shield className="h-4 w-4 mr-2" />
            Trust Bundles
          </TabsTrigger>
        </TabsList>

        <TabsContent value="contacts">
          <Card>
            <CardHeader>
              <CardTitle>Direct Address Book</CardTitle>
              <CardDescription>
                Verified healthcare providers and organizations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Direct Address</TableHead>
                    <TableHead>Organization</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Last Contact</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {addresses.map((addr) => (
                    <TableRow key={addr.id}>
                      <TableCell>
                        {addr.verified ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-yellow-500" />
                        )}
                      </TableCell>
                      <TableCell className="font-medium">{addr.name}</TableCell>
                      <TableCell className="text-sm font-mono">{addr.address}</TableCell>
                      <TableCell>{addr.organization}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {addr.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {addr.lastContact ? formatDate(addr.lastContact) : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trust">
          <Card>
            <CardHeader>
              <CardTitle>Trust Bundle Configuration</CardTitle>
              <CardDescription>
                Manage certificate trust anchors for Direct messaging
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Bundle Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Certificates</TableHead>
                    <TableHead>Last Updated</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {trustBundles.map((bundle) => (
                    <TableRow key={bundle.id}>
                      <TableCell>
                        <Badge
                          variant={bundle.status === "active" ? "default" : "secondary"}
                          className={bundle.status === "active" ? "bg-green-500" : ""}
                        >
                          {bundle.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{bundle.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{bundle.type}</Badge>
                      </TableCell>
                      <TableCell>{bundle.certCount.toLocaleString()}</TableCell>
                      <TableCell className="text-sm">
                        {new Date(bundle.lastUpdated).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm">
                            <RefreshCw className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Settings className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
